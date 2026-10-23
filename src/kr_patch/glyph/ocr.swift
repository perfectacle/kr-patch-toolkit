// Vision OCR: prints "<path>\t<text>\t<confidence>" for each image path argument.
import Foundation
import Vision
import AppKit

for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        print("\(path)\t\t0"); continue
    }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = [ProcessInfo.processInfo.environment["OCR_LANG"] ?? "ko-KR"]
    req.usesLanguageCorrection = false
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    let obs = req.results ?? []
    let best = obs.compactMap { $0.topCandidates(1).first }
    let text = best.map { $0.string }.joined(separator: " ")
    let conf = best.map { $0.confidence }.min() ?? 0
    print("\(path)\t\(text)\t\(conf)")
}
