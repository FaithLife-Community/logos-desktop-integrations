// One cover standing on the shelf. At rest it casts a soft shadow; on hover it lifts,
// tilts towards the pointer (a parallax "live photo" feel) and catches a moving sheen.
import QtQuick
import QtQuick.Effects
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami

Item {
    id: book
    required property var info
    property bool tiltEnabled: true
    signal open(string url)

    property real mx: 0.5
    property real my: 0.5
    property bool forceHover: false  // for previews/tests
    readonly property bool hovered: hit.containsMouse || forceHover

    Item {
        id: body
        anchors.fill: parent
        scale: book.hovered ? 1.07 : 1.0
        Behavior on scale { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

        transform: [
            Rotation {
                origin.x: body.width / 2; origin.y: body.height
                axis { x: 0; y: 1; z: 0 }
                angle: book.hovered && book.tiltEnabled ? (book.mx - 0.5) * 22 : 0
                Behavior on angle { SmoothedAnimation { velocity: 90 } }
            },
            Rotation {
                origin.x: body.width / 2; origin.y: body.height
                axis { x: 1; y: 0; z: 0 }
                angle: book.hovered && book.tiltEnabled ? (0.5 - book.my) * 16 : 0
                Behavior on angle { SmoothedAnimation { velocity: 90 } }
            },
            Translate {
                y: book.hovered ? -Kirigami.Units.smallSpacing * 2 : 0
                Behavior on y { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
            }
        ]

        Image {
            id: cover
            anchors.fill: parent
            source: book.info.cover ? "file://" + book.info.cover : ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            smooth: true
            mipmap: true
            visible: false
        }

        MultiEffect {
            source: cover
            anchors.fill: cover
            visible: cover.status === Image.Ready
            shadowEnabled: true
            shadowColor: "black"
            shadowOpacity: book.hovered ? 0.55 : 0.4
            shadowBlur: book.hovered ? 1.0 : 0.6
            shadowVerticalOffset: book.hovered ? 10 : 4
            shadowHorizontalOffset: book.hovered ? (0.5 - book.mx) * 10 : 2
            Behavior on shadowVerticalOffset { NumberAnimation { duration: 180 } }
        }

        // Fallback when there's no cover: a plain coloured board with the title.
        Rectangle {
            anchors.fill: parent
            visible: cover.status !== Image.Ready
            radius: 2
            color: Qt.hsla((book.info.title.length * 37 % 360) / 360, 0.35, 0.35, 1)
            PlasmaComponents.Label {
                anchors.fill: parent
                anchors.margins: Kirigami.Units.smallSpacing
                text: book.info.title
                color: "white"
                wrapMode: Text.Wrap
                elide: Text.ElideRight
                font: Kirigami.Theme.smallFont
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }

        // Spine: a little depth on the left edge.
        Rectangle {
            anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
            width: Math.max(3, parent.width * 0.05)
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, 0.35) }
                GradientStop { position: 0.6; color: Qt.rgba(1, 1, 1, 0.12) }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }

        // Sheen that slides with the pointer.
        Rectangle {
            anchors.fill: parent
            opacity: book.hovered ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 180 } }
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: Math.max(0, book.mx - 0.35); color: "transparent" }
                GradientStop { position: Math.min(1, Math.max(0.01, book.mx)); color: Qt.rgba(1, 1, 1, 0.22) }
                GradientStop { position: Math.min(1, book.mx + 0.35); color: "transparent" }
            }
        }
    }

    MouseArea {
        id: hit
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onPositionChanged: mouse => { book.mx = mouse.x / width; book.my = mouse.y / height }
        onExited: { book.mx = 0.5; book.my = 0.5 }
        onClicked: book.open(book.info.url)
    }

    PlasmaComponents.ToolTip {
        visible: book.hovered
        delay: 500
        text: book.info.title + (book.info.authors ? "\n" + book.info.authors : "")
              + "\n★ " + book.info.rating + "  (" + book.info.ratings + ")"
    }
}
