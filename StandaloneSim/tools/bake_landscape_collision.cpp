#include <nlohmann/json.hpp>

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace {

using Json = nlohmann::json;

struct FlatRectangle {
    std::size_t left = 0;
    std::size_t right = 0;
    std::size_t top = 0;
    std::size_t bottom = 0;
    std::size_t area = 0;
};

struct BakeResult {
    Json plane{};
    Json shore{};
    Json details{};
    std::size_t triangle_count = 0;
};

std::uint64_t DoubleBits(double value) {
    std::uint64_t result = 0;
    static_assert(sizeof(result) == sizeof(value));
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

Json LoadJson(const std::filesystem::path& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("Could not open " + path.string());
    Json result;
    input >> result;
    return result;
}

std::size_t DetectGridWidth(const Json& vertices) {
    if (!vertices.is_array() || vertices.size() < 4U) {
        throw std::runtime_error("Landscape has too few vertices.");
    }
    const std::uint64_t first_y = DoubleBits(vertices[0][1].get<double>());
    std::size_t width = 1U;
    while (width < vertices.size() && DoubleBits(vertices[width][1].get<double>()) == first_y) ++width;
    if (width < 2U || vertices.size() % width != 0U || vertices.size() / width < 2U) {
        throw std::runtime_error("Could not infer the landscape grid dimensions.");
    }
    return width;
}

std::uint64_t DominantHeightBits(const Json& vertices) {
    std::unordered_map<std::uint64_t, std::size_t> counts;
    counts.reserve(vertices.size() / 4U);
    std::uint64_t dominant = 0U;
    std::size_t dominant_count = 0U;
    for (const Json& vertex : vertices) {
        const std::uint64_t bits = DoubleBits(vertex[2].get<double>());
        const std::size_t count = ++counts[bits];
        if (count > dominant_count) {
            dominant = bits;
            dominant_count = count;
        }
    }
    return dominant;
}

FlatRectangle FindLargestFlatRectangle(
    const Json& vertices, std::size_t width, std::size_t height, std::uint64_t flat_height) {
    const std::size_t cell_width = width - 1U;
    const std::size_t cell_height = height - 1U;
    std::vector<std::size_t> histogram(cell_width, 0U);
    FlatRectangle best{};

    const auto is_flat = [&vertices, flat_height](std::size_t index) {
        return DoubleBits(vertices[index][2].get<double>()) == flat_height;
    };
    for (std::size_t y = 0; y < cell_height; ++y) {
        for (std::size_t x = 0; x < cell_width; ++x) {
            const std::size_t top_left = y * width + x;
            const bool flat = is_flat(top_left) && is_flat(top_left + 1U) &&
                is_flat(top_left + width) && is_flat(top_left + width + 1U);
            histogram[x] = flat ? histogram[x] + 1U : 0U;
        }

        std::vector<std::size_t> stack;
        stack.reserve(cell_width + 1U);
        for (std::size_t x = 0; x <= cell_width; ++x) {
            const std::size_t current = x < cell_width ? histogram[x] : 0U;
            while (!stack.empty() && histogram[stack.back()] > current) {
                const std::size_t index = stack.back();
                stack.pop_back();
                const std::size_t rectangle_height = histogram[index];
                const std::size_t left = stack.empty() ? 0U : stack.back() + 1U;
                const std::size_t area = rectangle_height * (x - left);
                if (area > best.area) {
                    best.left = left;
                    best.right = x - 1U;
                    best.bottom = y;
                    best.top = y - rectangle_height + 1U;
                    best.area = area;
                }
            }
            stack.push_back(x);
        }
    }
    if (best.area == 0U) throw std::runtime_error("Landscape has no rectangular exact-flat region.");
    return best;
}

Json CopyIdentity(const Json& source, const std::string& suffix, const std::string& source_name) {
    Json result = Json::object();
    result["id"] = source.value("id", std::string{}) + suffix;
    result["label"] = source.value("label", std::string{"Landscape"}) + source_name;
    result["actor_class"] = source.value("actor_class", std::string{});
    result["component"] = source.value("component", std::string{}) + suffix;
    return result;
}

BakeResult BakeLandscape(const Json& source, const std::string& input_name) {
    const Json& vertices = source.at("vertices");
    const Json& indices = source.at("indices");
    const std::size_t width = DetectGridWidth(vertices);
    const std::size_t height = vertices.size() / width;
    const std::size_t cell_width = width - 1U;
    const std::size_t cell_height = height - 1U;
    if (indices.size() != cell_width * cell_height * 2U) {
        throw std::runtime_error("Landscape triangle order does not match its regular grid.");
    }

    const std::uint64_t flat_height_bits = DominantHeightBits(vertices);
    const double flat_height = vertices[0][2].get<double>() == vertices[0][2].get<double>()
        ? [&]() {
            for (const Json& vertex : vertices) {
                if (DoubleBits(vertex[2].get<double>()) == flat_height_bits) return vertex[2].get<double>();
            }
            return 0.0;
        }()
        : 0.0;
    const FlatRectangle rectangle = FindLargestFlatRectangle(vertices, width, height, flat_height_bits);

    const std::size_t top_left = rectangle.top * width + rectangle.left;
    const std::size_t top_right = rectangle.top * width + rectangle.right + 1U;
    const std::size_t bottom_left = (rectangle.bottom + 1U) * width + rectangle.left;
    const std::size_t bottom_right = (rectangle.bottom + 1U) * width + rectangle.right + 1U;

    BakeResult result{};
    result.plane = CopyIdentity(source, ":flat_plane", " flat plane");
    result.plane["collision_source"] = "baked_flat_plane";
    result.plane["vertices"] = Json::array({
        vertices[top_left], vertices[top_right], vertices[bottom_right], vertices[bottom_left]});
    result.plane["indices"] = Json::array({Json::array({0, 1, 3}), Json::array({1, 2, 3})});

    result.shore = CopyIdentity(source, ":shore", " shore");
    result.shore["collision_source"] = "baked_shore_triangles";
    Json shore_vertices = Json::array();
    Json shore_indices = Json::array();
    auto& shore_vertex_array = shore_vertices.get_ref<Json::array_t&>();
    auto& shore_index_array = shore_indices.get_ref<Json::array_t&>();
    shore_vertex_array.reserve(vertices.size() - rectangle.area);
    shore_index_array.reserve(indices.size() - rectangle.area * 2U);
    std::unordered_map<std::size_t, std::size_t> remap;
    remap.reserve(vertices.size() - rectangle.area);

    for (std::size_t y = 0; y < cell_height; ++y) {
        for (std::size_t x = 0; x < cell_width; ++x) {
            const bool replaced_by_plane = x >= rectangle.left && x <= rectangle.right &&
                y >= rectangle.top && y <= rectangle.bottom;
            if (replaced_by_plane) continue;
            const std::size_t triangle_base = (y * cell_width + x) * 2U;
            for (std::size_t local_triangle = 0; local_triangle < 2U; ++local_triangle) {
                const Json& source_triangle = indices[triangle_base + local_triangle];
                Json output_triangle = Json::array();
                for (const Json& source_index_value : source_triangle) {
                    const std::size_t source_index = source_index_value.get<std::size_t>();
                    auto found = remap.find(source_index);
                    if (found == remap.end()) {
                        const std::size_t output_index = shore_vertex_array.size();
                        shore_vertex_array.push_back(vertices[source_index]);
                        found = remap.emplace(source_index, output_index).first;
                    }
                    output_triangle.push_back(found->second);
                }
                shore_index_array.push_back(std::move(output_triangle));
            }
        }
    }
    result.shore["vertices"] = std::move(shore_vertices);
    result.shore["indices"] = std::move(shore_indices);
    result.triangle_count = 2U + result.shore["indices"].size();

    result.details = {
        {"source", input_name},
        {"label", source.value("label", std::string{"Landscape"})},
        {"grid", Json::array({width, height})},
        {"flat_height_m", flat_height},
        {"plane_cell_bounds", Json::array({rectangle.left, rectangle.top, rectangle.right, rectangle.bottom})},
        {"plane_cells", rectangle.area},
        {"shore_triangles", result.shore["indices"].size()}};
    return result;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 4) {
        std::cerr << "Usage: prophecy_landscape_collision_baker <output.json> <landscape1.json> <landscape2.json>\n";
        return 2;
    }
    try {
        const std::filesystem::path output_path = argv[1];
        Json output = {
            {"schema", "prophecy.unreal-collision.v1"},
            {"coordinate_system", "prophecy_sim_xyz_meters"},
            {"objects", Json::array()},
            {"warnings", Json::array()},
            {"bake", {
                {"mode", "two_flat_planes_plus_exact_remaining_triangles"},
                {"rebuild", "manual_only"},
                {"landscapes", Json::array()}}}};

        std::string map_name;
        std::size_t triangle_count = 0U;
        for (int input_index = 2; input_index < 4; ++input_index) {
            const std::filesystem::path input_path = argv[input_index];
            const Json input = LoadJson(input_path);
            if (input.value("schema", std::string{}) != "prophecy.unreal-collision.v1" ||
                !input.contains("objects") || input["objects"].size() != 1U ||
                input["objects"][0].value("collision_source", std::string{}) != "landscape_heightfield") {
                throw std::runtime_error(input_path.string() + " is not one raw v1 landscape snapshot.");
            }
            const std::string input_map = input.value("map", std::string{});
            if (map_name.empty()) map_name = input_map;
            if (input_map != map_name) throw std::runtime_error("Input landscapes belong to different maps.");

            BakeResult baked = BakeLandscape(input["objects"][0], input_path.filename().string());
            output["objects"].push_back(std::move(baked.plane));
            output["objects"].push_back(std::move(baked.shore));
            output["bake"]["landscapes"].push_back(std::move(baked.details));
            triangle_count += baked.triangle_count;
            if (input.contains("warnings")) {
                for (const Json& warning : input["warnings"]) output["warnings"].push_back(warning);
            }
        }
        output["map"] = map_name;
        output["summary"] = {
            {"source_landscapes", 2},
            {"exported_objects", output["objects"].size()},
            {"triangles", triangle_count}};

        std::filesystem::create_directories(output_path.parent_path());
        std::ofstream stream(output_path, std::ios::binary | std::ios::trunc);
        if (!stream) throw std::runtime_error("Could not create " + output_path.string());
        stream << output;
        if (!stream) throw std::runtime_error("Could not finish writing " + output_path.string());
        std::cout << "Baked 2 planes and " << triangle_count - 4U
                  << " exact remaining triangles to " << output_path.string() << '\n';
        return 0;
    } catch (const std::exception& exception) {
        std::cerr << exception.what() << '\n';
        return 1;
    }
}
