import QtQuick
import org.kde.kirigami as Kirigami

Canvas {
    id: ring
    property real progress: 0
    property color color: Kirigami.Theme.positiveTextColor
    property color trackColor: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                       Kirigami.Theme.textColor.b, 0.15)
    property real thickness: Math.max(2, width / 9)

    onProgressChanged: requestPaint()
    onColorChanged: requestPaint()
    onWidthChanged: requestPaint()

    onPaint: {
        const ctx = getContext("2d")
        ctx.reset()
        const r = Math.min(width, height) / 2 - thickness / 2
        const cx = width / 2, cy = height / 2
        ctx.lineWidth = thickness
        ctx.lineCap = "round"
        ctx.strokeStyle = trackColor
        ctx.beginPath()
        ctx.arc(cx, cy, r, 0, 2 * Math.PI)
        ctx.stroke()
        if (progress > 0) {
            ctx.strokeStyle = color
            ctx.beginPath()
            const start = -Math.PI / 2
            ctx.arc(cx, cy, r, start, start + 2 * Math.PI * Math.min(1, Math.max(0.02, progress)))
            ctx.stroke()
        }
    }
}
