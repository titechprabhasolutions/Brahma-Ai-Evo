# gesture_utils.py
"""
Hand gesture recognition and classification utility for Brahma AI.

Recognizes:
- Open Palm (✋) -> Play / Pause
- Swipe Right (👉) -> Next Track / Next Slide
- Swipe Left (👈) -> Previous Track / Previous Slide
- Thumbs Up (👍) -> Volume Up
- Thumbs Down (👎) -> Volume Down
- Peace Sign (✌️) -> Instant Screenshot
- Pinch (🤏) -> Mouse Click
"""

import math
import time
from typing import Iterable, Optional


class GestureTracker:
    def __init__(self):
        # Hysteresis prevents the cursor click state flickering at the pinch boundary.
        self.prev_pinch = False
        self.pinch_on_ratio = 0.32
        self.pinch_off_ratio = 0.45
        self.last_palm_time = 0.0
        self.last_peace_time = 0.0
        self.last_swipe_time = 0.0
        self.last_volume_time = 0.0
        self.last_scroll_time = 0.0
        self.last_zoom_time = 0.0
        self.two_hand_distance_history: list[tuple[float, float]] = []
        self.palm_held_start = 0.0
        self.pos_history: list[tuple[float, float, float]] = []  # (x, y, timestamp)

    def reset(self) -> None:
        """Clear transient tracking state before a fresh camera session."""
        self.prev_pinch = False
        self.last_palm_time = 0.0
        self.last_peace_time = 0.0
        self.last_swipe_time = 0.0
        self.last_volume_time = 0.0
        self.last_scroll_time = 0.0
        self.last_zoom_time = 0.0
        self.two_hand_distance_history.clear()
        self.palm_held_start = 0.0
        self.pos_history.clear()


def orient_cursor_for_display(
    cursor: tuple[float, float],
    *,
    invert_x: bool = False,
    invert_y: bool = False,
) -> tuple[float, float]:
    """Apply optional axis inversion to normalized cursor coordinates.

    The camera preview is mirrored before MediaPipe runs, so the default is
    to preserve the detected coordinates. Inversion is an explicit UI option.
    """
    x, y = float(cursor[0]), float(cursor[1])
    if invert_x:
        x = 1.0 - x
    if invert_y:
        y = 1.0 - y
    return x, y


def estimate_gesture_state(
    landmarks: Optional[Iterable[tuple[float, float, float]]],
    screen_size: tuple[int, int] | bool | None = None,
    prev_pinch: bool = False,
    tracker: Optional[GestureTracker] = None,
) -> dict:
    """Translate hand landmarks into gesture state and high-level Air Actions."""
    if isinstance(screen_size, bool):
        prev_pinch = screen_size

    # MediaPipe returns lists, but accepting any iterable makes this utility safer
    # for tests and alternate camera pipelines too.
    landmarks = list(landmarks) if landmarks is not None else []
    if len(landmarks) < 21:
        if tracker:
            tracker.reset()
        return {
            "hand_detected": False,
            "cursor": None,
            "pinch": False,
            "pinch_triggered": False,
            "gesture_name": "None",
            "action": None,
        }

    now = time.monotonic()
    wrist = landmarks[0]
    thumb_tip = landmarks[4]
    thumb_ip = landmarks[3]
    thumb_mcp = landmarks[2]

    index_tip = landmarks[8]
    index_pip = landmarks[6]
    index_mcp = landmarks[5]

    middle_tip = landmarks[12]
    middle_pip = landmarks[10]
    middle_mcp = landmarks[9]

    ring_tip = landmarks[16]
    ring_pip = landmarks[14]

    pinky_tip = landmarks[20]
    pinky_pip = landmarks[18]

    # Finger open/closed state
    index_open = index_tip[1] < index_pip[1]
    middle_open = middle_tip[1] < middle_pip[1]
    ring_open = ring_tip[1] < ring_pip[1]
    pinky_open = pinky_tip[1] < pinky_pip[1]

    # Distance measurements
    palm_scale = max(0.01, math.hypot(middle_mcp[0] - wrist[0], middle_mcp[1] - wrist[1]))
    thumb_open = math.hypot(thumb_tip[0] - wrist[0], thumb_tip[1] - wrist[1]) > (palm_scale * 0.9)

    # Pinch detection (Thumb tip to Index tip)
    pinch_dist = math.hypot(thumb_tip[0] - index_tip[0], thumb_tip[1] - index_tip[1])
    # ULTRON-style hysteresis: enter a pinch at a tighter threshold, but keep
    # it active until the fingers separate farther. This avoids rapid
    # click/release flicker when landmarks jitter around one threshold.
    was_pinching = tracker.prev_pinch if tracker is not None else bool(prev_pinch)
    pinch_ratio = pinch_dist / palm_scale
    pinch_on = tracker.pinch_on_ratio if tracker is not None else 0.32
    pinch_off = tracker.pinch_off_ratio if tracker is not None else 0.45
    pinch = pinch_ratio < (pinch_off if was_pinching else pinch_on) or (
        pinch_dist < 0.055 and not was_pinching
    )
    pinch_triggered = bool(pinch and not was_pinching)
    if tracker is not None:
        tracker.prev_pinch = pinch

    # Cursor position (index fingertip normalized 0..1)
    cursor = (float(index_tip[0]), float(index_tip[1]))

    # Palm center position for swipe tracking
    palm_center_x = float(middle_mcp[0])
    palm_center_y = float(middle_mcp[1])

    gesture_name = "Open Hand"
    action = None

    # Track velocity for swipe gestures (👉 / 👈)
    swipe_action = None
    if tracker is not None:
        tracker.pos_history.append((palm_center_x, palm_center_y, now))
        # Keep last 0.35s
        tracker.pos_history = [p for p in tracker.pos_history if now - p[2] <= 0.35]

        if len(tracker.pos_history) >= 4:
            start_x, start_y, start_time = tracker.pos_history[0]
            end_x, end_y, end_time = tracker.pos_history[-1]
            dt = end_time - start_time
            dx = end_x - start_x
            dy = end_y - start_y
            three_finger_scroll = index_open and middle_open and ring_open and not pinky_open

            # Three raised fingers provide a deliberate vertical-scroll gesture.
            if three_finger_scroll and dt > 0.03 and abs(dy) > 0.14 and (now - tracker.last_scroll_time) > 0.55:
                swipe_action = "scroll_down" if dy > 0 else "scroll_up"
                gesture_name = "Three Finger Scroll ↓" if dy > 0 else "Three Finger Scroll ↑"
                tracker.last_scroll_time = now
                tracker.pos_history.clear()
            # Horizontal swipes retain the existing media/slide controls.
            elif (now - tracker.last_swipe_time) > 0.75 and dt > 0.03 and abs(dx) > 0.15:
                if dx > 0.15:
                    swipe_action = "swipe_right"
                    gesture_name = "Swipe Right 👉"
                    tracker.last_swipe_time = now
                elif dx < -0.15:
                    swipe_action = "swipe_left"
                    gesture_name = "Swipe Left 👈"
                    tracker.last_swipe_time = now

    if swipe_action:
        action = swipe_action

    elif pinch:
        gesture_name = "Pinch"

    # Three raised fingers are reserved for vertical scrolling (handled above).
    elif index_open and middle_open and ring_open and not pinky_open:
        gesture_name = "Three Finger Scroll"

    # ✌️ Peace Sign (Index + Middle open, Ring + Pinky closed) -> Screenshot
    elif index_open and middle_open and not ring_open and not pinky_open:
        gesture_name = "Peace ✌️"
        if tracker is not None:
            if now - tracker.last_peace_time > 2.0:
                action = "screenshot"
                tracker.last_peace_time = now
        else:
            action = "screenshot"

    # 👍 Thumbs Up (All 4 fingers closed, thumb pointing up) -> Volume Up
    elif not index_open and not middle_open and not ring_open and not pinky_open and (thumb_tip[1] < thumb_ip[1] < thumb_mcp[1]):
        gesture_name = "Thumbs Up 👍"
        if tracker is not None:
            if now - tracker.last_volume_time > 0.14:
                action = "volume_up"
                tracker.last_volume_time = now
        else:
            action = "volume_up"

    # 👎 Thumbs Down (All 4 fingers closed, thumb pointing down) -> Volume Down
    elif not index_open and not middle_open and not ring_open and not pinky_open and (thumb_tip[1] > thumb_ip[1] > thumb_mcp[1]):
        gesture_name = "Thumbs Down 👎"
        if tracker is not None:
            if now - tracker.last_volume_time > 0.14:
                action = "volume_down"
                tracker.last_volume_time = now
        else:
            action = "volume_down"

    # ✋ Open Palm (All 5 fingers extended) -> Play / Pause
    elif thumb_open and index_open and middle_open and ring_open and pinky_open:
        gesture_name = "Open Palm ✋"
        if tracker is not None:
            if tracker.palm_held_start == 0.0:
                tracker.palm_held_start = now
            elif (now - tracker.palm_held_start) >= 0.45 and (now - tracker.last_palm_time) > 1.4:
                action = "play_pause"
                tracker.last_palm_time = now
        else:
            action = "play_pause"
    else:
        if tracker is not None:
            tracker.palm_held_start = 0.0
        if index_open:
            gesture_name = "Pointer"

    return {
        "hand_detected": True,
        "cursor": cursor,
        "pinch": pinch,
        "pinch_triggered": pinch_triggered,
        "gesture_name": gesture_name,
        "action": action,
    }


def estimate_two_hand_zoom(
    hands: Optional[Iterable[Iterable[tuple[float, float, float]]]],
    tracker: Optional[GestureTracker] = None,
) -> Optional[str]:
    """Detect a deliberate two-hand spread/close motion as browser zoom."""
    if tracker is None:
        return None
    hand_list = [list(hand) for hand in (hands or [])]
    if len(hand_list) < 2 or any(len(hand) < 10 for hand in hand_list[:2]):
        tracker.two_hand_distance_history.clear()
        return None

    now = time.monotonic()
    centers = []
    for hand in hand_list[:2]:
        wrist, middle_mcp = hand[0], hand[9]
        centers.append(((wrist[0] + middle_mcp[0]) / 2.0, (wrist[1] + middle_mcp[1]) / 2.0))
    distance = math.hypot(centers[0][0] - centers[1][0], centers[0][1] - centers[1][1])

    history = tracker.two_hand_distance_history
    history.append((distance, now))
    tracker.two_hand_distance_history = [item for item in history if now - item[1] <= 0.45]
    history = tracker.two_hand_distance_history
    if len(history) < 3 or now - history[0][1] < 0.08 or now - tracker.last_zoom_time < 0.9:
        return None

    change = history[-1][0] - history[0][0]
    if change > 0.10:
        action = "zoom_in"
    elif change < -0.10:
        action = "zoom_out"
    else:
        return None

    tracker.last_zoom_time = now
    tracker.two_hand_distance_history.clear()
    return action
