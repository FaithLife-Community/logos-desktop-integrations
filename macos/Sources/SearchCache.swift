import Foundation

// This cache belongs to the integrations, not Logos. Raycast never needs a library UI.
enum SearchCache {
    #if LOGOS_LOCAL_DATA
    private static var path: URL {
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Logos Desktop Integrations/search.json")
    }
    #endif
    static func read() -> [LibraryItem] {
        #if LOGOS_LOCAL_DATA
        guard let data = try? Data(contentsOf: path) else { return [] }
        return (try? JSONDecoder().decode([LibraryItem].self, from: data)) ?? []
        #else
        return [] // Never load a previous full build's metadata cache.
        #endif
    }
    static func write(_ items: [LibraryItem]) {
        #if LOGOS_LOCAL_DATA
        let metadata = items.map { item -> LibraryItem in var item = item; item.cover = nil; return item }
        do {
            try FileManager.default.createDirectory(at: path.deletingLastPathComponent(), withIntermediateDirectories: true)
            try JSONEncoder().encode(metadata).write(to: path, options: .atomic)
        } catch { NSLog("Search cache: %@", error.localizedDescription) }
        #endif
    }
}
