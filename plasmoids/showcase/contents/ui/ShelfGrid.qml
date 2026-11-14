// One set of shelves: covers standing on planks that join into a continuous shelf.
import QtQuick
import org.kde.kirigami as Kirigami

GridView {
    id: grid
    property var shelf
    property bool fillLastPlank: true
    clip: true
    // Spread the books evenly across the width.
    // adaptive: scale the covers so whole rows exactly fill the available height
    property bool adaptive: false
    readonly property real chrome: shelf.plank + Kirigami.Units.gridUnit * 1.2
    readonly property real baseCell: shelf.bookHeight + chrome
    readonly property int rowsFit: Math.max(1, adaptive ? Math.round(height / baseCell) : Math.floor(height / baseCell))
    readonly property real bookH: adaptive && height > 0
        ? Math.max(Kirigami.Units.gridUnit * 4, Math.min(Kirigami.Units.gridUnit * 10, height / rowsFit - chrome))
        : shelf.bookHeight
    readonly property real bookW: bookH * 0.68
    readonly property int columns: Math.max(1, Math.floor(width / (bookW + Kirigami.Units.gridUnit)))
    cellWidth: width / columns
    cellHeight: adaptive && height > 0 ? height / rowsFit : bookH + chrome
    // how many books make whole rows in the visible height
    readonly property int fits: columns * rowsFit
    interactive: contentHeight > height

    delegate: Item {
        required property var modelData
        required property int index
        width: grid.cellWidth
        height: grid.cellHeight

        Book {
            info: parent.modelData
            tiltEnabled: shelf.widget.tilt
            width: grid.bookW
            height: grid.bookH
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: plank.top
            onOpen: url => shelf.widget.backend.openUrl(url)
            onHide: id => shelf.widget.hideBook(id)
        }

        // The shelf plank: adjacent cells join up into one continuous shelf.
        Rectangle {
            id: plank
            // the last book on a part-filled shelf extends the plank to the far edge
            readonly property bool lastOnShelf: grid.fillLastPlank && index === grid.count - 1
            anchors { left: parent.left; bottom: parent.bottom }
            width: lastOnShelf ? grid.width - parent.x : parent.width
            anchors.bottomMargin: Kirigami.Units.smallSpacing * 2
            height: shelf.plank
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.lighter(Kirigami.Theme.alternateBackgroundColor, 1.08) }
                GradientStop { position: 1.0; color: Qt.darker(Kirigami.Theme.alternateBackgroundColor, 1.25) }
            }
            Rectangle {  // soft shadow under the plank
                anchors { left: parent.left; right: parent.right; top: parent.bottom }
                height: Kirigami.Units.smallSpacing * 2
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, 0.18) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }
    }
}
