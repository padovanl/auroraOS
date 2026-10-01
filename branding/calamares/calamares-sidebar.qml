/* Aurora's installer header (Calamares "sidebar", placed on top: see
   branding.desc). The logo and name on the left, and the steps as a row of
   dots joined by a line: done ones filled with a tick, the current one glowing
   with its name in white, the rest dim. Nothing here needs the keyboard. */
import io.calamares.ui 1.0
import io.calamares.core 1.0

import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: header
    height: 96
    color: "#14101e"

    readonly property color accent: "#a970ff"
    readonly property color rose: "#ff6f91"
    readonly property color dim: "#3a3150"
    readonly property color text: "#cfc7dd"
    readonly property int current: ViewManager.currentStepIndex

    // A hairline under the header, fading at the ends.
    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.12) }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }

    Text {
        id: title
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 10
        text: qsTr("%1 Installer").arg(Branding.string(Branding.ProductName))
        color: "#efe9fa"
        font.pixelSize: 13
        font.weight: Font.DemiBold
        font.letterSpacing: 0.8
    }
    // Minimize and close, where a title bar has them.
    Row {
        anchors.right: parent.right
        anchors.rightMargin: 12
        anchors.verticalCenter: title.verticalCenter
        spacing: 8
        Repeater {
            model: [{ glyph: "−", action: "minimize" }, { glyph: "×", action: "close" }]
            Rectangle {
                width: 22; height: 22; radius: 11
                color: area.containsMouse
                       ? (modelData.action === "close" ? header.rose : Qt.rgba(1, 1, 1, 0.22))
                       : Qt.rgba(1, 1, 1, 0.09)
                Behavior on color { ColorAnimation { duration: 120 } }
                Text {
                    anchors.centerIn: parent
                    text: modelData.glyph
                    color: "white"
                    font.pixelSize: 15
                }
                MouseArea {
                    id: area
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: modelData.action === "close"
                               ? ViewManager.quit()
                               : Qt.openUrlExternally("aurora-installer:minimize")
                }
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.topMargin: 40
        anchors.leftMargin: 22
        anchors.rightMargin: 26
        spacing: 0

        // The steps.
        Row {
            id: steps
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            readonly property int count: repeater.count
            readonly property real cell: count > 0 ? width / count : width

            Repeater {
                id: repeater
                model: ViewManager
                Item {
                    width: steps.cell
                    height: 40
                    readonly property bool done: index < header.current
                    readonly property bool now: index === header.current

                    // Line to the next step.
                    Rectangle {
                        visible: index < steps.count - 1
                        x: parent.width / 2 + 11
                        y: 8
                        width: parent.width - 22
                        height: 2
                        radius: 1
                        color: done ? header.accent : header.dim
                        Behavior on color { ColorAnimation { duration: 250 } }
                    }
                    // Behind the current step, a soft halo that breathes, and a
                    // ring that keeps rippling outward from it.
                    Rectangle {
                        id: halo
                        visible: now
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 9 - height / 2
                        width: 26; height: 26; radius: 13
                        color: Qt.rgba(0.80, 0.50, 1.0, 0.5)
                        SequentialAnimation on scale {
                            running: now
                            loops: Animation.Infinite
                            NumberAnimation { from: 0.85; to: 1.35; duration: 1100; easing.type: Easing.InOutSine }
                            NumberAnimation { from: 1.35; to: 0.85; duration: 1100; easing.type: Easing.InOutSine }
                        }
                    }
                    Rectangle {
                        id: ripple
                        visible: now
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 9 - height / 2
                        width: 18; height: 18; radius: 9
                        color: "transparent"
                        border.width: 2
                        border.color: header.rose
                        ParallelAnimation {
                            running: now
                            loops: Animation.Infinite
                            NumberAnimation { target: ripple; property: "scale"; from: 1.0; to: 1.8; duration: 1800; easing.type: Easing.OutCubic }
                            NumberAnimation { target: ripple; property: "opacity"; from: 0.8; to: 0.0; duration: 1800; easing.type: Easing.OutCubic }
                        }
                    }
                    Rectangle {
                        id: dot
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: now ? 1 : 3
                        width: now ? 16 : 12
                        height: width
                        radius: width / 2
                        border.width: (done || now) ? 0 : 2
                        border.color: header.dim
                        gradient: Gradient {
                            GradientStop { position: 0; color: (done || now) ? header.accent : "#14101e" }
                            GradientStop { position: 1; color: now ? header.rose : ((done) ? header.accent : "#14101e") }
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: done
                            text: "✓"
                            color: "white"
                            font.pixelSize: 8
                            font.bold: true
                        }
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 21
                        width: parent.width - 6
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                        text: display
                        color: now ? "#ffffff" : (done ? header.text : "#8d8399")
                        font.pixelSize: 11
                        font.weight: now ? Font.DemiBold : Font.Normal
                    }
                }
            }
        }
    }
}
