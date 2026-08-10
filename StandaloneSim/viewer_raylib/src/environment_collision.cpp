#include "environment_collision.h"

#include "raymath.h"
#include "rlgl.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <limits>
#include <new>
#include <string>
#include <unordered_map>
#include <vector>

namespace prophecy::viewer {
namespace {

constexpr const char* kSchema = "prophecy.unreal-collision.v1";
constexpr std::size_t kMaximumTriangles = 5'000'000U;
constexpr std::size_t kMaximumIndexedVerticesPerMesh = 65'535U;
constexpr Color kDefaultCollisionSurface{64, 94, 105, 255};
constexpr Color kDirtSurface{128, 88, 48, 255};
constexpr Color kSandSurface{226, 193, 82, 255};
constexpr Color kWaterSurface{45, 125, 210, 255};
constexpr Color kHaySurface{228, 190, 58, 255};
constexpr Color kMountainSurface{218, 210, 210, 255};
constexpr float kAmbientLight = 0.44f;
constexpr float kDiffuseLight = 0.56f;
constexpr float kMountainAmbientLight = 0.68f;
constexpr float kMountainDirectionalDetail = 0.24f;
constexpr float kMountainSkyFill = 0.08f;

constexpr std::uint64_t kRenderCacheMagic =
    static_cast<std::uint64_t>('P') << 56U |
    static_cast<std::uint64_t>('C') << 48U |
    static_cast<std::uint64_t>('O') << 40U |
    static_cast<std::uint64_t>('L') << 32U |
    static_cast<std::uint64_t>('R') << 24U |
    static_cast<std::uint64_t>('E') << 16U |
    static_cast<std::uint64_t>('N') << 8U |
    static_cast<std::uint64_t>('D');
constexpr std::uint32_t kRenderCacheVersion = 1U;
constexpr std::uint32_t kMaximumCachedMeshes = 16'384U;
constexpr std::uint32_t kMaximumCachedMapNameBytes = 4'096U;

struct SourceSignature {
    std::uint64_t size = 0U;
    std::int64_t write_time = 0;
    bool valid = false;
};

struct RenderCacheHeader {
    std::uint64_t magic = kRenderCacheMagic;
    std::uint32_t version = kRenderCacheVersion;
    std::uint32_t mesh_count = 0U;
    std::uint64_t source_size = 0U;
    std::int64_t source_write_time = 0;
    std::uint64_t object_count = 0U;
    std::uint64_t triangle_count = 0U;
    std::uint64_t warning_count = 0U;
    std::uint32_t map_name_bytes = 0U;
    std::uint32_t reserved = 0U;
};

struct RenderCacheMeshHeader {
    std::uint32_t vertex_count = 0U;
    std::uint32_t triangle_count = 0U;
};

struct IndexedTriangle {
    std::array<std::size_t, 3U> vertices{};
    bool flat_shaded_mountain = false;
};

SourceSignature ReadSourceSignature(const std::string& path) {
    std::error_code error;
    const std::filesystem::path source(path);
    const std::uint64_t size = std::filesystem::file_size(source, error);
    if (error) return {};
    const auto write_time = std::filesystem::last_write_time(source, error);
    if (error) return {};
    return {size, static_cast<std::int64_t>(write_time.time_since_epoch().count()), true};
}

bool SameSignature(const SourceSignature& first, const SourceSignature& second) {
    return first.valid && second.valid && first.size == second.size &&
        first.write_time == second.write_time;
}

std::filesystem::path RenderCachePath(const std::string& source_path) {
    std::filesystem::path result(source_path);
    result += ".rendercache";
    return result;
}

void ReleaseMeshCpuMemory(Mesh& mesh) {
    if (mesh.vertices != nullptr) MemFree(mesh.vertices);
    if (mesh.colors != nullptr) MemFree(mesh.colors);
    if (mesh.indices != nullptr) MemFree(mesh.indices);
    mesh = {};
}

void UnloadCachedMeshes(std::vector<Mesh>& meshes) {
    for (Mesh& mesh : meshes) UnloadMesh(mesh);
    meshes.clear();
}

bool LoadRenderCache(const std::string& source_path, const SourceSignature& source_signature,
    std::vector<Mesh>& meshes, std::size_t& object_count, std::size_t& triangle_count,
    std::size_t& warning_count, std::string& map_name) {
    if (!source_signature.valid) return false;
    std::ifstream input(RenderCachePath(source_path), std::ios::binary);
    if (!input) return false;
    RenderCacheHeader header{};
    input.read(reinterpret_cast<char*>(&header), sizeof(header));
    if (!input || header.magic != kRenderCacheMagic ||
        header.version != kRenderCacheVersion ||
        header.mesh_count == 0U || header.mesh_count > kMaximumCachedMeshes ||
        header.map_name_bytes > kMaximumCachedMapNameBytes ||
        header.source_size != source_signature.size ||
        header.source_write_time != source_signature.write_time ||
        header.triangle_count == 0U || header.triangle_count > kMaximumTriangles) {
        return false;
    }

    std::string cached_map(header.map_name_bytes, '\0');
    input.read(cached_map.data(), static_cast<std::streamsize>(cached_map.size()));
    if (!input) return false;

    std::vector<Mesh> cached_meshes;
    cached_meshes.reserve(header.mesh_count);
    std::uint64_t cached_triangle_count = 0U;
    for (std::uint32_t index = 0U; index < header.mesh_count; ++index) {
        RenderCacheMeshHeader mesh_header{};
        input.read(reinterpret_cast<char*>(&mesh_header), sizeof(mesh_header));
        if (!input || mesh_header.vertex_count == 0U ||
            mesh_header.vertex_count > kMaximumIndexedVerticesPerMesh ||
            mesh_header.triangle_count == 0U ||
            mesh_header.triangle_count > kMaximumTriangles - cached_triangle_count) {
            UnloadCachedMeshes(cached_meshes);
            return false;
        }
        Mesh mesh{};
        mesh.vertexCount = static_cast<int>(mesh_header.vertex_count);
        mesh.triangleCount = static_cast<int>(mesh_header.triangle_count);
        const std::size_t position_bytes =
            static_cast<std::size_t>(mesh_header.vertex_count) * 3U * sizeof(float);
        const std::size_t color_bytes =
            static_cast<std::size_t>(mesh_header.vertex_count) * 4U;
        const std::size_t index_bytes =
            static_cast<std::size_t>(mesh_header.triangle_count) * 3U * sizeof(unsigned short);
        mesh.vertices = static_cast<float*>(MemAlloc(static_cast<unsigned int>(position_bytes)));
        mesh.colors = static_cast<unsigned char*>(MemAlloc(static_cast<unsigned int>(color_bytes)));
        mesh.indices = static_cast<unsigned short*>(MemAlloc(static_cast<unsigned int>(index_bytes)));
        if (mesh.vertices == nullptr || mesh.colors == nullptr || mesh.indices == nullptr) {
            ReleaseMeshCpuMemory(mesh);
            UnloadCachedMeshes(cached_meshes);
            return false;
        }
        input.read(reinterpret_cast<char*>(mesh.vertices),
            static_cast<std::streamsize>(position_bytes));
        input.read(reinterpret_cast<char*>(mesh.colors),
            static_cast<std::streamsize>(color_bytes));
        input.read(reinterpret_cast<char*>(mesh.indices),
            static_cast<std::streamsize>(index_bytes));
        if (!input) {
            ReleaseMeshCpuMemory(mesh);
            UnloadCachedMeshes(cached_meshes);
            return false;
        }
        UploadMesh(&mesh, false);
        cached_meshes.push_back(mesh);
        cached_triangle_count += mesh_header.triangle_count;
    }
    if (cached_triangle_count != header.triangle_count) {
        UnloadCachedMeshes(cached_meshes);
        return false;
    }

    meshes.swap(cached_meshes);
    object_count = static_cast<std::size_t>(header.object_count);
    triangle_count = static_cast<std::size_t>(header.triangle_count);
    warning_count = static_cast<std::size_t>(header.warning_count);
    map_name.swap(cached_map);
    return true;
}

void SaveRenderCache(const std::string& source_path, const SourceSignature& source_signature,
    const std::vector<Mesh>& meshes, const std::size_t object_count,
    const std::size_t triangle_count, const std::size_t warning_count,
    const std::string& map_name) {
    if (!source_signature.valid || meshes.empty() ||
        map_name.size() > kMaximumCachedMapNameBytes) return;
    const std::filesystem::path cache_path = RenderCachePath(source_path);
    std::filesystem::path temporary_path = cache_path;
    temporary_path += ".tmp";
    std::ofstream output(temporary_path, std::ios::binary | std::ios::trunc);
    if (!output) return;
    RenderCacheHeader header{};
    header.mesh_count = static_cast<std::uint32_t>(meshes.size());
    header.source_size = source_signature.size;
    header.source_write_time = source_signature.write_time;
    header.object_count = object_count;
    header.triangle_count = triangle_count;
    header.warning_count = warning_count;
    header.map_name_bytes = static_cast<std::uint32_t>(map_name.size());
    output.write(reinterpret_cast<const char*>(&header), sizeof(header));
    output.write(map_name.data(), static_cast<std::streamsize>(map_name.size()));
    for (const Mesh& mesh : meshes) {
        if (mesh.vertexCount <= 0 || mesh.triangleCount <= 0 ||
            mesh.vertices == nullptr || mesh.colors == nullptr || mesh.indices == nullptr) {
            output.setstate(std::ios::failbit);
            break;
        }
        RenderCacheMeshHeader mesh_header{
            static_cast<std::uint32_t>(mesh.vertexCount),
            static_cast<std::uint32_t>(mesh.triangleCount)};
        output.write(reinterpret_cast<const char*>(&mesh_header), sizeof(mesh_header));
        output.write(reinterpret_cast<const char*>(mesh.vertices),
            static_cast<std::streamsize>(mesh.vertexCount) * 3 * sizeof(float));
        output.write(reinterpret_cast<const char*>(mesh.colors),
            static_cast<std::streamsize>(mesh.vertexCount) * 4);
        output.write(reinterpret_cast<const char*>(mesh.indices),
            static_cast<std::streamsize>(mesh.triangleCount) * 3 * sizeof(unsigned short));
    }
    output.close();
    std::error_code error;
    if (!output) {
        std::filesystem::remove(temporary_path, error);
        return;
    }
    std::filesystem::remove(cache_path, error);
    error.clear();
    std::filesystem::rename(temporary_path, cache_path, error);
    if (error) {
        error.clear();
        std::filesystem::remove(temporary_path, error);
    }
}

bool ReadVertex(const nlohmann::json& value, Vector3& result) {
    if (!value.is_array() || value.size() != 3U) return false;
    for (const auto& coordinate : value) {
        if (!coordinate.is_number()) return false;
    }
    // Snapshot coordinates use the sim convention (X/Y ground plane, Z up).
    // raylib uses X/Z as its ground plane.
    result = {value[0].get<float>(), value[2].get<float>(), value[1].get<float>()};
    return true;
}

Color SurfaceColor(const nlohmann::json& object) {
    const std::string source = object.value("collision_source", std::string{});
    const std::string label = object.value("label", std::string{});
    if (source == "baked_flat_plane") return kDirtSurface;
    if (source == "baked_shore_triangles") return kSandSurface;
    if (source == "unreal_water_plane") return kWaterSurface;
    if (label.rfind("Hay", 0U) == 0U) return kHaySurface;
    if (source == "complex_mountain") return kMountainSurface;
    return kDefaultCollisionSurface;
}

Vector3 DirectionToLight(const nlohmann::json& root) {
    // The cached vector is Unreal's directional-light forward direction in the
    // shared X/Y/Z convention: the direction in which the light travels.
    Vector3 unreal_forward{0.4863177f, -0.1161780f, -0.8660241f};
    const auto value = root.find("directional_light_direction");
    if (value != root.end() && value->is_array() && value->size() == 3U &&
        (*value)[0].is_number() && (*value)[1].is_number() && (*value)[2].is_number()) {
        unreal_forward = {(*value)[0].get<float>(), (*value)[1].get<float>(),
            (*value)[2].get<float>()};
    }
    // Convert to raylib's X/Z ground plane and point from the surface to the light.
    const Vector3 direction_to_light{-unreal_forward.x, -unreal_forward.z, -unreal_forward.y};
    const float length_squared = Vector3LengthSqr(direction_to_light);
    return length_squared > 1.0e-8f
        ? Vector3Scale(direction_to_light, 1.0f / std::sqrt(length_squared))
        : Vector3{0.0f, 1.0f, 0.0f};
}

Color ShadeColor(const Color base, const Vector3 normal, const Vector3 direction_to_light) {
    const float length_squared = Vector3LengthSqr(normal);
    const Vector3 unit_normal = length_squared > 1.0e-8f
        ? Vector3Scale(normal, 1.0f / std::sqrt(length_squared))
        : Vector3{0.0f, 1.0f, 0.0f};
    const float diffuse = std::max(Vector3DotProduct(unit_normal, direction_to_light), 0.0f);
    const float illumination = kAmbientLight + kDiffuseLight * diffuse;
    const auto shade = [illumination](const unsigned char channel) {
        return static_cast<unsigned char>(std::clamp(
            static_cast<int>(std::lround(static_cast<float>(channel) * illumination)), 0, 255));
    };
    return {shade(base.r), shade(base.g), shade(base.b), base.a};
}

Color ShadeMountainColor(const Vector3 normal, const Vector3 direction_to_light) {
    const float length_squared = Vector3LengthSqr(normal);
    const Vector3 unit_normal = length_squared > 1.0e-8f
        ? Vector3Scale(normal, 1.0f / std::sqrt(length_squared))
        : Vector3{0.0f, 1.0f, 0.0f};
    // Complex mountain triangles are cached flat-shaded. A two-sided
    // directional term preserves real face-to-face geometric variation while
    // the high ambient and sky fill keep back-facing ranges readable.
    const float directional_detail = std::fabs(
        Vector3DotProduct(unit_normal, direction_to_light));
    const float sky_fill = std::max(unit_normal.y, 0.0f);
    const float illumination = std::clamp(kMountainAmbientLight +
        kMountainDirectionalDetail * directional_detail +
        kMountainSkyFill * sky_fill, 0.0f, 1.0f);
    const auto shade = [illumination](const unsigned char channel) {
        return static_cast<unsigned char>(std::clamp(
            static_cast<int>(std::lround(static_cast<float>(channel) * illumination)), 0, 255));
    };
    return {shade(kMountainSurface.r), shade(kMountainSurface.g),
        shade(kMountainSurface.b), kMountainSurface.a};
}

}  // namespace

bool EnvironmentCollision::Load(const std::string& path, std::string& error) {
    Shutdown();

    const SourceSignature initial_signature = ReadSourceSignature(path);
    if (LoadRenderCache(path, initial_signature, meshes_, object_count_, triangle_count_,
            warning_count_, map_name_)) {
        material_ = LoadMaterialDefault();
        material_.maps[MATERIAL_MAP_DIFFUSE].color = WHITE;
        loaded_ = true;
        return true;
    }

    std::ifstream input(path);
    if (!input) {
        error = "Could not open Unreal collision snapshot: " + path;
        return false;
    }

    nlohmann::json root;
    try {
        input >> root;
    } catch (const nlohmann::json::exception& exception) {
        error = "Invalid Unreal collision snapshot '" + path + "': " + exception.what();
        return false;
    }

    if (!root.is_object() || root.value("schema", std::string{}) != kSchema) {
        error = "Unsupported Unreal collision snapshot schema: " + path;
        return false;
    }
    const auto objects = root.find("objects");
    if (objects == root.end() || !objects->is_array()) {
        error = "Unreal collision snapshot has no objects array: " + path;
        return false;
    }
    const auto warnings = root.find("warnings");
    if (warnings != root.end()) {
        if (!warnings->is_array()) {
            error = "Unreal collision snapshot has an invalid warnings array: " + path;
            return false;
        }
        warning_count_ = warnings->size();
    }

    std::vector<Vector3> all_vertices;
    std::vector<Color> all_colors;
    std::vector<IndexedTriangle> all_triangles;
    for (const auto& object : *objects) {
        if (!object.is_object()) {
            error = "Unreal collision snapshot contains a non-object entry: " + path;
            return false;
        }
        const auto vertices = object.find("vertices");
        const auto indices = object.find("indices");
        if (vertices == object.end() || !vertices->is_array() ||
            indices == object.end() || !indices->is_array()) {
            error = "Unreal collision object is missing vertices or indices: " + path;
            return false;
        }
        if (indices->size() > kMaximumTriangles - triangle_count_) {
            error = "Unreal collision snapshot exceeds the five-million-triangle debug limit.";
            return false;
        }

        const std::size_t object_vertex_base = all_vertices.size();
        const Color object_color = SurfaceColor(object);
        const bool flat_shaded_mountain =
            object.value("collision_source", std::string{}) == "complex_mountain";
        all_vertices.reserve(all_vertices.size() + vertices->size());
        all_colors.reserve(all_colors.size() + vertices->size());
        for (const auto& vertex : *vertices) {
            Vector3 parsed{};
            if (!ReadVertex(vertex, parsed)) {
                error = "Unreal collision snapshot contains an invalid vertex: " + path;
                return false;
            }
            all_vertices.push_back(parsed);
            all_colors.push_back(object_color);
        }

        for (const auto& triangle : *indices) {
            if (!triangle.is_array() || triangle.size() != 3U ||
                !triangle[0].is_number_unsigned() || !triangle[1].is_number_unsigned() ||
                !triangle[2].is_number_unsigned()) {
                error = "Unreal collision snapshot contains an invalid triangle: " + path;
                return false;
            }
            const std::size_t first = triangle[0].get<std::size_t>();
            const std::size_t second = triangle[1].get<std::size_t>();
            const std::size_t third = triangle[2].get<std::size_t>();
            if (first >= vertices->size() || second >= vertices->size() ||
                third >= vertices->size()) {
                error = "Unreal collision snapshot contains an out-of-range triangle: " + path;
                return false;
            }
            // The sim-to-raylib axis swap changes handedness, so reverse winding.
            all_triangles.push_back({{object_vertex_base + first,
                object_vertex_base + third, object_vertex_base + second},
                flat_shaded_mountain});
            ++triangle_count_;
        }
        ++object_count_;
    }

    if (triangle_count_ == 0U) {
        error = "Unreal collision snapshot contains no triangles: " + path;
        Shutdown();
        return false;
    }

    // The environment is static between cache updates. Bake one smooth normal
    // and the level-light contribution into each existing vertex color once so
    // normal frames retain the same cheap unlit vertex-color draw path.
    std::vector<Vector3> accumulated_normals(all_vertices.size(), Vector3{});
    for (const IndexedTriangle& triangle : all_triangles) {
        if (triangle.flat_shaded_mountain) continue;
        const Vector3& first = all_vertices[triangle.vertices[0]];
        const Vector3& second = all_vertices[triangle.vertices[1]];
        const Vector3& third = all_vertices[triangle.vertices[2]];
        Vector3 normal = Vector3CrossProduct(
            Vector3Subtract(second, first), Vector3Subtract(third, first));
        const float length_squared = Vector3LengthSqr(normal);
        if (length_squared <= 1.0e-12f) continue;
        normal = Vector3Scale(normal, 1.0f / std::sqrt(length_squared));
        for (const std::size_t vertex : triangle.vertices) {
            accumulated_normals[vertex] = Vector3Add(accumulated_normals[vertex], normal);
        }
    }
    const Vector3 direction_to_light = DirectionToLight(root);
    for (std::size_t index = 0; index < all_colors.size(); ++index) {
        all_colors[index] = ShadeColor(all_colors[index], accumulated_normals[index], direction_to_light);
    }

    std::vector<float> chunk_positions;
    std::vector<unsigned char> chunk_colors;
    std::vector<unsigned short> chunk_indices;
    std::unordered_map<std::size_t, unsigned short> chunk_vertex_indices;
    chunk_positions.reserve(kMaximumIndexedVerticesPerMesh * 3U);
    chunk_colors.reserve(kMaximumIndexedVerticesPerMesh * 4U);
    chunk_vertex_indices.reserve(kMaximumIndexedVerticesPerMesh);

    const auto flush_chunk = [&]() -> bool {
        if (chunk_indices.empty()) return true;
        Mesh mesh{};
        mesh.vertexCount = static_cast<int>(chunk_positions.size() / 3U);
        mesh.triangleCount = static_cast<int>(chunk_indices.size() / 3U);
        const unsigned int position_bytes = static_cast<unsigned int>(chunk_positions.size() * sizeof(float));
        const unsigned int color_bytes = static_cast<unsigned int>(chunk_colors.size());
        const unsigned int index_bytes = static_cast<unsigned int>(chunk_indices.size() * sizeof(unsigned short));
        mesh.vertices = static_cast<float*>(MemAlloc(position_bytes));
        mesh.colors = static_cast<unsigned char*>(MemAlloc(color_bytes));
        mesh.indices = static_cast<unsigned short*>(MemAlloc(index_bytes));
        if (mesh.vertices == nullptr || mesh.colors == nullptr || mesh.indices == nullptr) {
            if (mesh.vertices != nullptr) MemFree(mesh.vertices);
            if (mesh.colors != nullptr) MemFree(mesh.colors);
            if (mesh.indices != nullptr) MemFree(mesh.indices);
            return false;
        }
        std::copy(chunk_positions.begin(), chunk_positions.end(), mesh.vertices);
        std::copy(chunk_colors.begin(), chunk_colors.end(), mesh.colors);
        std::copy(chunk_indices.begin(), chunk_indices.end(), mesh.indices);
        UploadMesh(&mesh, false);
        meshes_.push_back(mesh);
        chunk_positions.clear();
        chunk_colors.clear();
        chunk_indices.clear();
        chunk_vertex_indices.clear();
        return true;
    };

    for (const IndexedTriangle& triangle : all_triangles) {
        std::size_t new_vertex_count = triangle.flat_shaded_mountain ? 3U : 0U;
        if (!triangle.flat_shaded_mountain) {
            for (const std::size_t vertex : triangle.vertices) {
                if (chunk_vertex_indices.find(vertex) == chunk_vertex_indices.end()) ++new_vertex_count;
            }
        }
        if (!chunk_indices.empty() &&
            chunk_positions.size() / 3U + new_vertex_count > kMaximumIndexedVerticesPerMesh &&
            !flush_chunk()) {
            error = "Could not allocate an Unreal collision debug mesh chunk.";
            Shutdown();
            return false;
        }
        if (triangle.flat_shaded_mountain) {
            const Vector3& first = all_vertices[triangle.vertices[0]];
            const Vector3& second = all_vertices[triangle.vertices[1]];
            const Vector3& third = all_vertices[triangle.vertices[2]];
            const Vector3 face_normal = Vector3CrossProduct(
                Vector3Subtract(second, first), Vector3Subtract(third, first));
            const Color face_color = ShadeMountainColor(face_normal, direction_to_light);
            for (const std::size_t vertex_index : triangle.vertices) {
                const unsigned short local_index =
                    static_cast<unsigned short>(chunk_positions.size() / 3U);
                const Vector3& vertex = all_vertices[vertex_index];
                chunk_positions.push_back(vertex.x);
                chunk_positions.push_back(vertex.y);
                chunk_positions.push_back(vertex.z);
                chunk_colors.push_back(face_color.r);
                chunk_colors.push_back(face_color.g);
                chunk_colors.push_back(face_color.b);
                chunk_colors.push_back(face_color.a);
                chunk_indices.push_back(local_index);
            }
            continue;
        }
        for (const std::size_t vertex_index : triangle.vertices) {
            auto found = chunk_vertex_indices.find(vertex_index);
            if (found == chunk_vertex_indices.end()) {
                const unsigned short local_index = static_cast<unsigned short>(chunk_positions.size() / 3U);
                const Vector3& vertex = all_vertices[vertex_index];
                chunk_positions.push_back(vertex.x);
                chunk_positions.push_back(vertex.y);
                chunk_positions.push_back(vertex.z);
                const Color color = all_colors[vertex_index];
                chunk_colors.push_back(color.r);
                chunk_colors.push_back(color.g);
                chunk_colors.push_back(color.b);
                chunk_colors.push_back(color.a);
                found = chunk_vertex_indices.emplace(vertex_index, local_index).first;
            }
            chunk_indices.push_back(found->second);
        }
    }
    if (!flush_chunk()) {
        error = "Could not allocate an Unreal collision debug mesh chunk.";
        Shutdown();
        return false;
    }
    material_ = LoadMaterialDefault();
    material_.maps[MATERIAL_MAP_DIFFUSE].color = WHITE;
    map_name_ = root.value("map", std::string{});
    loaded_ = true;
    const SourceSignature final_signature = ReadSourceSignature(path);
    if (SameSignature(initial_signature, final_signature)) {
        SaveRenderCache(path, final_signature, meshes_, object_count_, triangle_count_,
            warning_count_, map_name_);
    }
    return true;
}

bool EnvironmentCollision::Reload(const std::string& path, std::string& error) {
    EnvironmentCollision replacement{};
    if (!replacement.Load(path, error)) return false;
    meshes_.swap(replacement.meshes_);
    std::swap(material_, replacement.material_);
    std::swap(object_count_, replacement.object_count_);
    std::swap(triangle_count_, replacement.triangle_count_);
    std::swap(warning_count_, replacement.warning_count_);
    map_name_.swap(replacement.map_name_);
    std::swap(loaded_, replacement.loaded_);
    replacement.Shutdown();
    return true;
}

void EnvironmentCollision::Draw() const noexcept {
    if (!loaded_) return;
    // Collision shells remain readable if the debug camera is inside one.
    rlDisableBackfaceCulling();
    for (const Mesh& mesh : meshes_) DrawMesh(mesh, material_, MatrixIdentity());
    rlEnableBackfaceCulling();
}

void EnvironmentCollision::Shutdown() noexcept {
    for (Mesh& mesh : meshes_) UnloadMesh(mesh);
    if (material_.maps != nullptr) UnloadMaterial(material_);
    meshes_.clear();
    material_ = {};
    object_count_ = 0U;
    triangle_count_ = 0U;
    warning_count_ = 0U;
    map_name_.clear();
    loaded_ = false;
}

}  // namespace prophecy::viewer
