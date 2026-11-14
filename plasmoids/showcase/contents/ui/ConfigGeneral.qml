import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    property alias cfg_bookCount: count.value
    property alias cfg_tilt: tilt.checked
    property var cfg_hiddenBooks: []

    QQC2.Button {
        visible: cfg_hiddenBooks.length > 0
        text: i18np("Show %1 hidden book again", "Show %1 hidden books again", cfg_hiddenBooks.length)
        onClicked: cfg_hiddenBooks = []
    }

    Kirigami.FormLayout {
        QQC2.SpinBox {
            id: count
            Kirigami.FormData.label: i18n("Books (at most):")
            from: 3; to: 36
        }
        QQC2.CheckBox {
            id: tilt
            Kirigami.FormData.label: i18n("Effects:")
            text: i18n("Tilt covers towards the pointer")
        }
    }
}
