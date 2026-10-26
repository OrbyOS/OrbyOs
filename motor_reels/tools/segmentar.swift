// Extrae los fotogramas de un vídeo de iPhone en SDR (BT.709) y la silueta de la persona.
// Uso: segmentar <video> <carpeta_salida> [rangos]
// Escribe f_00000.jpg (fotograma) y m_00000.png (máscara en el canal alfa) por cada fotograma.
// [rangos]: «a-b,c-d» en números de fotograma; solo se escriben esos (brutos largos: los tramos que usan los reels).
import AVFoundation
import CoreImage
import Foundation
import Vision

let args = CommandLine.arguments
guard args.count == 3 || args.count == 4 else { print("uso: segmentar <video> <salida> [rangos]"); exit(1) }
let rangos: [ClosedRange<Int>] = args.count == 4 ? args[3].split(separator: ",").compactMap { r in
    let p = r.split(separator: "-").compactMap { Int($0) }
    return p.count == 2 && p[0] <= p[1] ? p[0]...p[1] : nil
} : []
func seUsa(_ n: Int) -> Bool { rangos.isEmpty || rangos.contains { $0.contains(n) } }
let url = URL(fileURLWithPath: args[1])
let out = URL(fileURLWithPath: args[2], isDirectory: true)
try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)

let asset = AVURLAsset(url: url)
let sema = DispatchSemaphore(value: 0)
var track: AVAssetTrack!
var comp: AVMutableVideoComposition!
Task {
    track = try! await asset.loadTracks(withMediaType: .video).first!
    comp = try! await AVMutableVideoComposition.videoComposition(withPropertiesOf: asset)
    sema.signal()
}
sema.wait()

// Pedir la salida en BT.709 hace que AVFoundation convierta el HLG a SDR.
comp.colorPrimaries = AVVideoColorPrimaries_ITU_R_709_2
comp.colorTransferFunction = AVVideoTransferFunction_ITU_R_709_2
comp.colorYCbCrMatrix = AVVideoYCbCrMatrix_ITU_R_709_2

let reader = try! AVAssetReader(asset: asset)
let output = AVAssetReaderVideoCompositionOutput(
    videoTracks: [track],
    videoSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
output.videoComposition = comp
reader.add(output)
reader.startReading()

let ctx = CIContext()
let srgb = CGColorSpace(name: CGColorSpace.sRGB)!
let request = VNGeneratePersonSegmentationRequest()
request.qualityLevel = .accurate
request.outputPixelFormat = kCVPixelFormatType_OneComponent8

var i = 0
while let sample = output.copyNextSampleBuffer() {
    guard let pb = CMSampleBufferGetImageBuffer(sample) else { continue }
    if !seUsa(i) { i += 1; continue }
    let frame = CIImage(cvPixelBuffer: pb)
    let name = String(format: "%05d", i)
    try! ctx.writeJPEGRepresentation(
        of: frame, to: out.appendingPathComponent("f_\(name).jpg"), colorSpace: srgb,
        options: [kCGImageDestinationLossyCompressionQuality as CIImageRepresentationOption: 0.98])

    let handler = VNImageRequestHandler(cvPixelBuffer: pb, options: [:])
    try! handler.perform([request])
    if let mask = request.results?.first?.pixelBuffer {
        var m = CIImage(cvPixelBuffer: mask)
        m = m.transformed(by: CGAffineTransform(
            scaleX: frame.extent.width / m.extent.width, y: frame.extent.height / m.extent.height))
        // Negro opaco donde está la persona, transparente fuera: sirve como mask-image en CSS.
        let black = CIImage(color: .black).cropped(to: frame.extent)
        let clear = CIImage(color: .clear).cropped(to: frame.extent)
        let rgba = black.applyingFilter("CIBlendWithMask", parameters: [
            kCIInputBackgroundImageKey: clear, kCIInputMaskImageKey: m])
        try! ctx.writePNGRepresentation(
            of: rgba, to: out.appendingPathComponent("m_\(name).png"), format: .RGBA8, colorSpace: srgb)
    }
    i += 1
    if i % 60 == 0 { print("\(i) fotogramas") }
}
print("listo: \(i) fotogramas")
