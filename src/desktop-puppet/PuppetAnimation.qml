import QtQuick

Item {
    id: character
    objectName: "characterAnimation"
    property bool playing: true
    property int frameIndex: 0
    property real hoverOffset: 0
    function gesture() {
        if (playing)
            cycle.restart()
    }
    Image {
        anchors.centerIn: parent
        width: 320; height: 320
        source: "qrc:/assets/puppet-hover.png"
        sourceClipRect: Qt.rect((character.frameIndex % 3) * 512,
                               Math.floor(character.frameIndex / 3) * 512, 512, 512)
        transform: Translate { y: character.hoverOffset }
        smooth: false
        mipmap: false
    }
    // Floating displacement complements the drawn elbow/knee changes; it
    // never rotates the whole character. Pause freezes both kinds of motion.
    SequentialAnimation {
        running: true
        paused: !character.playing
        loops: Animation.Infinite
        NumberAnimation { target: character; property: "hoverOffset"; from: 0; to: -10; duration: 1495; easing.type: Easing.InOutSine }
        NumberAnimation { target: character; property: "hoverOffset"; from: -10; to: 0; duration: 1495; easing.type: Easing.InOutSine }
    }
    // Brief closing/opening frames keep the blink short; the resting pose
    // holds between gestures instead of continuously waving at the user.
    SequentialAnimation {
        id: cycle
        running: true
        paused: !character.playing
        loops: Animation.Infinite
        PropertyAction { target: character; property: "frameIndex"; value: 1 }
        PauseAnimation { duration: 320 }
        PropertyAction { target: character; property: "frameIndex"; value: 2 }
        PauseAnimation { duration: 120 }
        PropertyAction { target: character; property: "frameIndex"; value: 3 }
        PauseAnimation { duration: 110 }
        PropertyAction { target: character; property: "frameIndex"; value: 4 }
        PauseAnimation { duration: 320 }
        PropertyAction { target: character; property: "frameIndex"; value: 5 }
        PauseAnimation { duration: 320 }
        PropertyAction { target: character; property: "frameIndex"; value: 0 }
        PauseAnimation { duration: 1800 }
    }
}
