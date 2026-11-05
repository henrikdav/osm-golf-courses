// The text of a PDF's pages as JSON, read with macOS' PDFKit (golf/slope.py reads slope tables with it): each line
// with where it is on the page, as the reading order of a table's columns can't be trusted.
//   swift tools/pdftext.swift file.pdf  →  [[{"text", "x", "y", "w", "h"}, …], …]  (one list per page; y up)
import Foundation
import PDFKit

guard CommandLine.arguments.count == 2, let doc = PDFDocument(url: URL(fileURLWithPath: CommandLine.arguments[1])) else {
    FileHandle.standardError.write("usage: pdftext.swift file.pdf\n".data(using: .utf8)!)
    exit(1)
}
let pages: [[[String: Any]]] = (0..<doc.pageCount).map { i in
    guard let page = doc.page(at: i), let all = page.selection(for: page.bounds(for: .mediaBox)) else { return [] }
    return all.selectionsByLine().compactMap { line in
        let text = (line.string ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return nil }
        let b = line.bounds(for: page)
        return ["text": text, "x": Double(b.minX), "y": Double(b.minY), "w": Double(b.width), "h": Double(b.height)]
    }
}
let data = try JSONSerialization.data(withJSONObject: pages)
print(String(data: data, encoding: .utf8)!)
