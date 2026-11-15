import QtQuick
import "PuppetMotion.js" as Motion

Item {
    id: character
    objectName: "characterAnimation"
    property bool playing: true
    property var player: new Motion.Player()
    property int frameIndex: 36
    property string animationKind: "idle"
    property real hoverOffset: 0
    property real idleMotionAmount: 1
    property bool ready: false
    onFrameIndexChanged: canvas.requestPaint()
    onAnimationKindChanged: canvas.requestPaint()

    function gesture() {
        if (playing) player.giggle()
    }
    function advance(dt) {
        player.tick(dt)
        animationKind = player.mode
        frameIndex = animationKind === "giggle" ? Motion.giggleState(player.giggleTime).cell : player.frame
        hoverOffset = 7 * Math.sin(player.time * 2.2)
        // Ease idle head and arm motion out before the hands move in and restore it
        // during the final hold. Keep the body's hover continuous.
        var target = animationKind !== "giggle" || player.giggleTime >= 2600 ? 1 : 0
        idleMotionAmount += Math.max(-dt / .35, Math.min(dt / .35, target - idleMotionAmount))
        canvas.requestPaint()
    }
    onPlayingChanged: clock.previous = Date.now()

    Timer {
        id: clock
        property real previous: Date.now()
        interval: 16
        repeat: true
        running: character.playing && character.ready
        onRunningChanged: previous = Date.now()
        onTriggered: {
            var now = Date.now()
            character.advance(Math.max(0, Math.min(.05, (now - previous) / 1000)))
            previous = now
        }
    }
    Canvas {
        id: canvas
        anchors.centerIn: parent
        anchors.verticalCenterOffset: character.hoverOffset * scale
        // Paint the approved deformation at its original pixel resolution;
        // scaling individual four-pixel bands creates seams at desktop size.
        width: 512; height: 544
        scale: .625
        property url idleAtlas: "qrc:/assets/puppet-idle.png"
        property url giggleAtlas: "qrc:/assets/puppet-giggle.png"
        readonly property var armRows: [168, 208, 224, 240, 256, 272, 288]
        function drawIdleArms(ctx, atlas, sx, sy, sourceScale, bob, time, amount) {
            if (amount < .001) {
                ctx.drawImage(atlas, sx, sy+168*sourceScale, 512*sourceScale, 120*sourceScale,
                              0, bob+168, 512, 120)
                return
            }
            // Connected strips bend the existing arms without cutting out
            // joints. Shared pixel edges avoid the seams from antialiased tiles.
            for (var x = 0; x < 512; x += 4) {
                if (x < 96 || (x >= 240 && x < 308) || x >= 440) {
                    ctx.drawImage(atlas, sx+x*sourceScale, sy+168*sourceScale, 4*sourceScale, 120*sourceScale,
                                  x, bob+168, 4, 120)
                    continue
                }
                for (var row = 0; row < armRows.length-1; ++row) {
                    var y = armRows[row], endY = armRows[row+1]
                    var top = Math.round(y + amount * Motion.idleArmOffset(x+2, y, time))
                    var bottom = Math.round(endY + amount * Motion.idleArmOffset(x+2, endY, time))
                    ctx.drawImage(atlas, sx+x*sourceScale, sy+y*sourceScale, 4*sourceScale, (endY-y)*sourceScale,
                                  x, bob+top, 4, bottom-top)
                }
            }
        }
        Component.onCompleted: { loadImage(idleAtlas); loadImage(giggleAtlas) }
        onImageLoaded: { character.ready = isImageLoaded(idleAtlas) && isImageLoaded(giggleAtlas); requestPaint() }
        onPaint: {
            if (!character.ready) return
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, 512, 544)
            ctx.save()
            var bob = 16
            var t = character.player.time
            var tilt = (.018*Math.sin(t*.92) + .006*Math.sin(t*1.43)) * character.idleMotionAmount
            var dx = .65*Math.sin(t*.73) * character.idleMotionAmount
            var dy = .45*Math.sin(t*1.1) * character.idleMotionAmount
            var sx, sy
            if (character.animationKind === "idle") {
                var n = character.frameIndex - 1
                sx = (n % 6) * 256; sy = Math.floor(n / 6) * 256
                ctx.drawImage(idleAtlas, sx, sy+144, 256, 112, 0, bob+288, 512, 224)
                drawIdleArms(ctx, idleAtlas, sx, sy, .5, bob, t, character.idleMotionAmount)
                ctx.save()
                ctx.translate(273+dx, bob+171+dy)
                ctx.rotate(tilt)
                ctx.drawImage(idleAtlas, sx, sy, 256, 86, -273, -171, 512, 172)
                ctx.restore()
            } else {
                sx = (character.frameIndex % 4) * 512; sy = Math.floor(character.frameIndex / 4) * 512
                var bounce = Motion.giggleBounce(Motion.giggleState(character.player.giggleTime))
                ctx.save()
                ctx.translate(0, bob)
                if (character.frameIndex === 0) {
                    // Both resting ends of the giggle share the idle arm
                    // motion, eased to zero before her hands move inward.
                    ctx.drawImage(giggleAtlas, sx, sy+288, 512, 224, 0, 288, 512, 224)
                    drawIdleArms(ctx, giggleAtlas, sx, sy, 1, 0, t, character.idleMotionAmount)
                    ctx.drawImage(giggleAtlas, sx, sy+160, 512, 8, 0, 160, 512, 8)
                } else if (bounce < .001) {
                    ctx.drawImage(giggleAtlas, sx, sy+260, 512, 252, 0, 260, 512, 252)
                    ctx.drawImage(giggleAtlas, sx, sy+160, 512, 100, 0, 160, 512, 100)
                } else {
                    ctx.drawImage(giggleAtlas, sx, sy+260, 512, 252, 0, 260, 512, 252)
                    for (var x = 0; x < 512; x += 16) {
                        for (var y = 160; y < 260; y += 4) {
                            // Share exact pixel boundaries between adjacent bands.
                            // Qt antialiases fractional edges separately, causing
                            // transparent seams even when the rectangles overlap.
                            var top = Math.round(y + Motion.shoulderOffset(x+8, y, bounce))
                            var bottom = Math.round(y+4 + Motion.shoulderOffset(x+8, y+4, bounce))
                            ctx.drawImage(giggleAtlas, sx+x, sy+y, 16, 4, x, top, 16, bottom-top)
                        }
                    }
                }
                ctx.translate(273+dx, 171+dy)
                ctx.rotate(tilt)
                ctx.drawImage(giggleAtlas, sx, sy, 512, 160, -273, -171, 512, 160)
                ctx.restore()
            }
            ctx.restore()
        }
    }
}
