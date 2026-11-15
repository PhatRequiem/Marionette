// Frame numbers preserve the approved pose map. This module has no desktop or
// personal-data access; the same clock drives drawing and the animation state.
function Player(random) {
    this.random = random || Math.random;
    this.pose = "down";
    this.frame = 36;
    this.clip = [];
    this.clipKind = "";
    this.elapsed = 0;
    this.hold = this.range(2, 7);
    this.blinkIn = this.range(3, 6);
    this.totalHold = 0;
    this.mode = "idle";
    this.giggleTime = 0;
    this.pendingGiggle = false;
    this.time = 0;
}
Player.prototype.range = function(a, b) { return a + this.random() * (b - a); };
Player.prototype.startClip = function(kind, frames) {
    this.clipKind = kind;
    this.clip = frames.slice();
    this.elapsed = 0;
    this.frame = this.clip.shift();
};
Player.prototype.giggle = function() {
    // Coalesce clicks, and finish any blink/transition before lowering the legs.
    if (this.mode === "idle") this.pendingGiggle = true;
};
Player.prototype.tick = function(dt) {
    this.time += dt;
    if (this.mode === "giggle") {
        this.giggleTime += dt * 1000;
        if (this.giggleTime >= giggleDuration) {
            this.mode = "idle";
            this.frame = 36;
            this.hold = this.range(2, 7);
            this.totalHold = 0;
        }
        return;
    }
    if (this.clipKind) {
        this.elapsed += dt;
        while (this.clipKind) {
            var duration = this.clipKind === "blink" ? (this.clip.length > 6 ? 0.035 : 0.055) : 0.14;
            if (this.elapsed < duration) break;
            this.elapsed -= duration;
            if (this.clip.length) this.frame = this.clip.shift();
            else {
                var ended = this.clipKind;
                this.clipKind = "";
                if (ended === "to-up") this.pose = "up";
                if (ended === "to-down") this.pose = "down";
                this.frame = this.pose === "up" ? 24 : 36;
                if (ended !== "blink") {
                    this.hold = this.range(2, 7);
                    this.totalHold = 0;
                }
                this.blinkIn = this.range(3, 6);
            }
        }
        return;
    }
    if (this.pendingGiggle) {
        if (this.pose === "up") this.startClip("to-down", [24,31,32,33,34,35,36]);
        else {
            this.pendingGiggle = false;
            this.mode = "giggle";
            this.giggleTime = 0;
        }
        return;
    }
    this.hold -= dt;
    this.totalHold += dt;
    if (this.pose === "up") this.blinkIn -= dt;
    if (this.hold <= 0) {
        if (this.random() < 0.65 || this.totalHold >= 14) {
            if (this.pose === "down") this.startClip("to-up", [36,35,34,33,32,31,24]);
            else this.startClip("to-down", [24,31,32,33,34,35,36]);
        } else this.hold = this.range(2, 7);
    }
    if (!this.clipKind && this.pose === "up" && this.blinkIn <= 0)
        this.startClip("blink", [24,37,38,39,40,41,42,41,40,39,38,37,24]);
};
var giggleTimeline = [
    [0,480,"rest"], [1,120,"in"], [2,120,"in"], [3,120,"kick"],
    [4,120,"kick"], [5,120,"kick"], [6,120,"kick"],
    [5,120,"kick"], [4,120,"kick"], [3,120,"kick"],
    [4,120,"kick"], [5,120,"kick"], [6,120,"kick"],
    [5,120,"kick"], [4,120,"kick"], [3,120,"kick"],
    [2,160,"reset"], [1,160,"reset"], [0,900,"rest"]
];
var giggleDuration = 3500;
function giggleState(ms) {
    var remaining = Math.max(0, ms);
    for (var i = 0; i < giggleTimeline.length; ++i) {
        var state = giggleTimeline[i];
        if (remaining < state[1]) return {cell:state[0], phase:state[2], local:ms};
        remaining -= state[1];
    }
    return {cell:0, phase:"rest", local:ms};
}
function giggleBounce(state) {
    if (state.phase === "rest") return 0;
    var t = Math.max(0, (state.local - 480) / 1000);
    var phase = t % 1.22;
    var pulse = Math.exp(-Math.pow((phase-.16)/.055,2))
        + .78*Math.exp(-Math.pow((phase-.39)/.065,2))
        + .48*Math.exp(-Math.pow((phase-.62)/.075,2));
    var settle = state.phase === "reset" ? Math.max(0,1-(state.local-2280)/320) : 1;
    return 5.2 * pulse * Math.min(1,t/.18) * settle;
}
function shoulderOffset(x, y, bounce) {
    if (y <= 160 || y >= 260) return 0;
    var u = y <= 200 ? (y-160)/40 : (260-y)/60;
    var taper = u*u*(3-2*u);
    var shoulders = Math.min(1, Math.exp(-Math.pow((x-218)/29,2))
        + Math.exp(-Math.pow((x-322)/29,2))
        + .15*Math.exp(-Math.pow((x-270)/55,2)));
    return -bounce * taper * shoulders;
}

function smoothStep(value) {
    var u = Math.max(0, Math.min(1, value));
    return u*u*(3-2*u);
}

function idleArmOffset(x, y, time) {
    if (x >= 242 && x <= 308) return 0;
    var left = x < 242;
    var distance = left ? 242-x : x-308;
    // The sleeve leads, then the elbow and wrist follow. Different phases
    // keep the two arms from rising and falling in perfect unison.
    var phase = time * 1.7 + (left ? 0 : .65);
    var lift = 2 * Math.sin(phase) * smoothStep(distance / 40)
        + 6 * Math.sin(phase-.3) * smoothStep((distance-12) / 54)
        + 8 * Math.sin(phase-.75) * smoothStep((distance-58) / 58);
    // Below the elbows, exclude the bodice and skirt. The last taper lies
    // in transparent space beneath the fingertips, preserving the hand shape.
    var inset = Math.max(0, y-212) * 1.2;
    var outsideBody = smoothStep((distance-inset) / 32);
    var bottom = 1 - smoothStep((y-248) / 40);
    return lift * outsideBody * bottom;
}
