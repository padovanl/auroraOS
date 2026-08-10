/* Aurora OS installer slideshow (shown while files are copied). */
import QtQuick 2.0
import calamares.slideshow 1.0

Presentation {
    id: presentation

    Timer {
        interval: 8000
        running: presentation.activatedInCalamares
        repeat: true
        onTriggered: presentation.goToNextSlide()
    }

    // Fill the whole slideshow area; Calamares otherwise shows its white base colour
    // around the slides.
    Rectangle {
        z: -1
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#1b1428" }
            GradientStop { position: 1.0; color: "#0d0a14" }
        }
    }

    component AuroraSlide: Slide {
        property string heading
        property string body
        property string image

        // The default Slide geometry leaves margins; use the whole area.
        x: 0
        y: 0
        width: presentation.width
        height: presentation.height

        Text {
            id: headingText
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height * 0.05
            text: heading
            font.pixelSize: Math.max(20, parent.height * 0.055)
            font.weight: Font.DemiBold
            color: "#f2eefa"
        }
        Text {
            id: bodyText
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: headingText.bottom
            anchors.topMargin: 8
            width: parent.width * 0.86
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: body
            font.pixelSize: Math.max(13, parent.height * 0.032)
            lineHeight: 1.2
            color: "#cfc7dd"
        }
        Rectangle {
            id: frame
            readonly property real maxW: parent.width * 0.86
            readonly property real maxH: parent.height - bodyText.y - bodyText.height - 36
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: bodyText.bottom
            anchors.topMargin: 18
            width: Math.min(maxW, maxH * 16 / 9) + 2
            height: width * 9 / 16
            radius: 6
            color: "#3a2f52"
            Image {
                anchors.fill: parent
                anchors.margins: 1
                source: image
                fillMode: Image.PreserveAspectFit
                smooth: true
                asynchronous: true
            }
        }
    }

    AuroraSlide {
        heading: qsTr("Welcome to Aurora OS")
        body: qsTr("A calm, fast desktop on the rock-solid Debian base. Sit back — this takes a few minutes.")
        image: "slides/welcome.jpg"
    }
    AuroraSlide {
        heading: qsTr("Find anything with Super")
        body: qsTr("Apps, files, settings, quick math, unit and currency conversion, clipboard history and commands — all from one search.")
        image: "slides/spotlight.jpg"
    }
    AuroraSlide {
        heading: qsTr("Built for developers")
        body: qsTr("Git, compilers, Python, Node.js, containers and a modern terminal are ready. Dev Hub installs editors, languages and databases in one click.")
        image: "slides/developers.jpg"
    }
    AuroraSlide {
        heading: qsTr("A private AI assistant")
        body: qsTr("Chat, writing tools, dictation and read-aloud run on your computer, in your language. Nothing leaves it unless you choose a cloud service.")
        image: "slides/ai.jpg"
    }
    AuroraSlide {
        heading: qsTr("Make it yours")
        body: qsTr("Pick a layout, move the dock and panel, choose accent colors, fonts and a wallpaper that follows the time of day.")
        image: "slides/yours.jpg"
    }
    AuroraSlide {
        heading: qsTr("Play anything")
        body: qsTr("Game Hub sets up Steam with Proton, Epic and GOG, Windows programs and Android apps — each in one click.")
        image: "slides/games.jpg"
    }
    AuroraSlide {
        heading: qsTr("Safe and healthy")
        body: qsTr("Security updates install by themselves, the firewall is on, a snapshot is taken before every update, and System Health keeps an eye on everything.")
        image: "slides/safe.jpg"
    }
}
