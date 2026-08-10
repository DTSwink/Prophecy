#include <nlohmann/json.hpp>

#include <cstddef>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_set>

namespace {

using Json = nlohmann::json;
constexpr const char* kSchema = "prophecy.unreal-collision.v1";

Json ReadSnapshot(const std::filesystem::path& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("Could not open collision snapshot: " + path.string());
    Json root;
    input >> root;
    if (!root.is_object() || root.value("schema", std::string{}) != kSchema ||
        !root.contains("objects") || !root["objects"].is_array()) {
        throw std::runtime_error("Unsupported collision snapshot: " + path.string());
    }
    return root;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 4) {
            std::cerr << "Usage: prophecy_collision_replacer <base.json> "
                         "<replacement.json> <output.json>\n";
            return 2;
        }
        Json base = ReadSnapshot(argv[1]);
        Json replacement = ReadSnapshot(argv[2]);
        if (base.value("map", std::string{}) != replacement.value("map", std::string{})) {
            throw std::runtime_error("Base and replacement snapshots are from different maps.");
        }

        std::unordered_set<std::string> labels;
        for (const Json& object : replacement["objects"]) {
            if (!object.is_object()) throw std::runtime_error("Replacement contains an invalid object.");
            const std::string label = object.value("label", std::string{});
            if (label.empty()) throw std::runtime_error("Replacement object has no actor label.");
            labels.insert(label);
        }
        if (labels.empty()) throw std::runtime_error("Replacement snapshot is empty.");

        Json merged_objects = Json::array();
        auto& merged_array = merged_objects.get_ref<Json::array_t&>();
        merged_array.reserve(base["objects"].size() + replacement["objects"].size());
        for (Json& object : base["objects"]) {
            if (!object.is_object()) throw std::runtime_error("Base contains an invalid object.");
            if (labels.find(object.value("label", std::string{})) == labels.end()) {
                merged_array.push_back(std::move(object));
            }
        }
        for (Json& object : replacement["objects"]) {
            merged_array.push_back(std::move(object));
        }
        base["objects"] = std::move(merged_objects);

        Json warnings = base.value("warnings", Json::array());
        if (!warnings.is_array()) warnings = Json::array();
        std::unordered_set<std::string> warning_text;
        for (const Json& warning : warnings) {
            if (warning.is_string()) warning_text.insert(warning.get<std::string>());
        }
        const Json replacement_warnings = replacement.value("warnings", Json::array());
        if (replacement_warnings.is_array()) {
            for (const Json& warning : replacement_warnings) {
                if (warning.is_string() && warning_text.insert(warning.get<std::string>()).second) {
                    warnings.push_back(warning);
                }
            }
        }
        base["warnings"] = std::move(warnings);

        std::size_t triangle_count = 0U;
        std::size_t complex_object_count = 0U;
        for (const Json& object : base["objects"]) {
            if (!object.contains("indices") || !object["indices"].is_array()) {
                throw std::runtime_error("Merged object is missing triangle indices.");
            }
            triangle_count += object["indices"].size();
            if (labels.find(object.value("label", std::string{})) != labels.end() &&
                object.value("collision_source", std::string{}).find("complex") != std::string::npos) {
                ++complex_object_count;
            }
        }
        if (complex_object_count != replacement["objects"].size()) {
            throw std::runtime_error("Not every replacement object is marked as complex collision.");
        }
        base["summary"]["exported_objects"] = base["objects"].size();
        base["summary"]["triangles"] = triangle_count;

        const std::filesystem::path output_path = argv[3];
        std::filesystem::create_directories(output_path.parent_path());
        std::ofstream output(output_path, std::ios::trunc);
        if (!output) throw std::runtime_error("Could not create merged collision snapshot.");
        output << base.dump(1) << '\n';
        if (!output) throw std::runtime_error("Could not finish merged collision snapshot.");
        std::cout << "Replaced " << labels.size() << " actor(s) with "
                  << complex_object_count << " complex object(s); merged cache has "
                  << base["objects"].size() << " objects and " << triangle_count
                  << " triangles.\n";
        return 0;
    } catch (const std::exception& exception) {
        std::cerr << exception.what() << '\n';
        return 1;
    }
}
