import Foundation

// This flag gates all Logos-folder discovery, SQLite code, data-derived UI and indexing.
// A commands-only binary cannot re-enable those features with preferences or arguments.
enum BuildFeatures {
    #if LOGOS_LOCAL_DATA
    static let localData = true
    #else
    static let localData = false
    #endif
}

struct LibraryItem: Codable, Identifiable, Hashable {
    var id: String
    var title: String
    var subtitle: String = ""
    var url: String
    var category: String
    var progress: Double? = nil
    var dueDate: String? = nil
    var reminder: String? = nil
    var cover: Data? = nil
    var resourceID: String? = nil
    var abbreviation: String? = nil
    var rating: Double? = nil
    var kind: String? = nil
    var priority: Int? = nil
    var uses: Int? = nil
    var language: String? = nil
    var planKind: String? = nil
    var streak: Int? = nil
    var minutes: Int? = nil
    var daysBehind: Int? = nil
}

struct IntegrationSnapshot: Codable {
    var updated = Date()
    var items: [LibraryItem] = []
    var message = "Open Logos Desktop Integrations to refresh."
}

enum SharedStore {
    static var container: URL? {
        guard let group = Bundle.main.object(forInfoDictionaryKey: "SharedGroupIdentifier") as? String else { return nil }
        return FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: group)
    }
    static func read() -> IntegrationSnapshot {
        guard let url = container?.appendingPathComponent("snapshot.json"),
              let data = try? Data(contentsOf: url),
              var snapshot = try? JSONDecoder().decode(IntegrationSnapshot.self, from: data) else {
            return IntegrationSnapshot(message: "Open Logos Desktop Integrations. Widget sharing requires a signed App Group build.")
        }
        #if !LOGOS_LOCAL_DATA
        // Ignore any data-derived cache left by a previously installed full build.
        snapshot.items.removeAll { $0.category != "pinned" }
        #endif
        return snapshot
    }
    static func write(_ snapshot: IntegrationSnapshot) throws {
        guard let container else { return }
        try FileManager.default.createDirectory(at: container, withIntermediateDirectories: true)
        try JSONEncoder().encode(snapshot).write(to: container.appendingPathComponent("snapshot.json"), options: .atomic)
    }
    static func commandURL(_ command: String) -> String { actionURL(command, kind: "command") }
    static func actionURL(_ command: String, kind: String) -> String {
        var parts = URLComponents()
        parts.scheme = "logos-integrations"
        parts.host = kind
        parts.queryItems = [URLQueryItem(name: "q", value: command)]
        return parts.string ?? "logos-integrations:"
    }
}
