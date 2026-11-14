import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    property string cfg_shelf: "library"
    property alias cfg_bookCount: count.value
    property alias cfg_tilt: tilt.checked
    property var cfg_hiddenBooks: []

    QQC2.Button {
        visible: cfg_hiddenBooks.length > 0
        text: i18np("Show %1 hidden book again", "Show %1 hidden books again", cfg_hiddenBooks.length)
        onClicked: cfg_hiddenBooks = []
    }

    Kirigami.FormLayout {
        QQC2.ComboBox {
            id: shelfChoice
            Kirigami.FormData.label: i18n("Shelf:")
            textRole: "text"
            valueRole: "value"
            model: [
                { text: i18n("Unread and well rated"), value: "library" },
                { text: i18n("Commentaries for your sermon"), value: "sermon" }
            ]
            currentIndex: Math.max(0, indexOfValue(cfg_shelf))
            onActivated: cfg_shelf = currentValue
        }
        QQC2.Label {
            visible: cfg_shelf === "sermon"
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.Wrap
            opacity: 0.7
            text: i18n("Commentaries you rated 4–5★ covering the passage of your next (or latest) sermon document, opening at that passage. If you've rated none, the best community-rated ones. Add a second Showcase widget to have both shelves.")
        }
        QQC2.SpinBox {
            id: count
            Kirigami.FormData.label: i18n("Books (at most):")
            from: 3; to: 72
        }
        QQC2.CheckBox {
            id: tilt
            Kirigami.FormData.label: i18n("Effects:")
            text: i18n("Tilt covers towards the pointer")
        }
    }
}
