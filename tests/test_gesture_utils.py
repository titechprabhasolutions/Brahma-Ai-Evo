from gesture_utils import (
    GestureTracker,
    estimate_gesture_state,
    orient_cursor_for_display,
)


def _landmarks_with_pinch_distance(distance: float):
    landmarks = [(0.5, 0.5, 0.0)] * 21
    landmarks[0] = (0.0, 0.0, 0.0)   # wrist
    landmarks[9] = (0.0, 1.0, 0.0)   # palm scale = 1
    landmarks[4] = (0.0, 0.2, 0.0)   # thumb tip
    landmarks[8] = (distance, 0.2, 0.0)  # index tip
    return landmarks


def test_estimate_gesture_state_reports_no_hand_when_missing_landmarks():
    state = estimate_gesture_state(None, (1920, 1080))
    assert state["hand_detected"] is False
    assert state["cursor"] is None


def test_estimate_gesture_state_detects_pinch_trigger():
    landmarks = [(0.2, 0.2, 0.0)] * 21
    landmarks[4] = (0.2, 0.2, 0.0)
    landmarks[8] = (0.2, 0.2, 0.0)
    state = estimate_gesture_state(landmarks, (1920, 1080), False)
    assert state["pinch"] is True
    assert state["pinch_triggered"] is True


def test_pinch_hysteresis_prevents_flicker_near_release_threshold():
    tracker = GestureTracker()

    pressed = estimate_gesture_state(_landmarks_with_pinch_distance(0.20), tracker=tracker)
    assert pressed["pinch"] is True
    assert pressed["pinch_triggered"] is True

    # 0.40 is outside the 0.32 activation threshold but inside the 0.45
    # release threshold, so the pinch remains held without another click.
    held = estimate_gesture_state(_landmarks_with_pinch_distance(0.40), tracker=tracker)
    assert held["pinch"] is True
    assert held["pinch_triggered"] is False

    released = estimate_gesture_state(_landmarks_with_pinch_distance(0.50), tracker=tracker)
    assert released["pinch"] is False
    assert released["pinch_triggered"] is False


def test_losing_hand_resets_pinch_state():
    tracker = GestureTracker()
    estimate_gesture_state(_landmarks_with_pinch_distance(0.20), tracker=tracker)
    assert tracker.prev_pinch is True

    missing = estimate_gesture_state(None, tracker=tracker)
    assert missing["hand_detected"] is False
    assert tracker.prev_pinch is False


def test_tracker_reset_clears_transient_session_state():
    tracker = GestureTracker()
    tracker.prev_pinch = True
    tracker.last_palm_time = 10.0
    tracker.last_peace_time = 11.0
    tracker.last_swipe_time = 12.0
    tracker.last_volume_time = 13.0
    tracker.palm_held_start = 14.0
    tracker.pos_history.append((0.4, 0.5, 15.0))

    tracker.reset()

    assert tracker.prev_pinch is False
    assert tracker.last_palm_time == 0.0
    assert tracker.last_peace_time == 0.0
    assert tracker.last_swipe_time == 0.0
    assert tracker.last_volume_time == 0.0
    assert tracker.palm_held_start == 0.0
    assert tracker.pos_history == []


def _three_finger_landmarks(y_offset: float = 0.0):
    points = [(0.5, 0.5 + y_offset, 0.0)] * 21
    points[0] = (0.5, 0.8 + y_offset, 0.0)   # wrist
    points[9] = (0.5, 0.5 + y_offset, 0.0)   # palm center / scale
    points[4] = (0.5, 0.7 + y_offset, 0.0)   # thumb stays closed
    points[8] = (0.42, 0.2 + y_offset, 0.0)
    points[6] = (0.42, 0.3 + y_offset, 0.0)
    points[12] = (0.50, 0.18 + y_offset, 0.0)
    points[10] = (0.50, 0.28 + y_offset, 0.0)
    points[16] = (0.58, 0.22 + y_offset, 0.0)
    points[14] = (0.58, 0.32 + y_offset, 0.0)
    points[20] = (0.66, 0.42 + y_offset, 0.0)
    points[18] = (0.66, 0.35 + y_offset, 0.0)
    return points


def test_three_finger_vertical_motion_scrolls_down(monkeypatch):
    tracker = GestureTracker()
    ticks = iter([1.00, 1.05, 1.10, 1.15])
    monkeypatch.setattr("gesture_utils.time.monotonic", lambda: next(ticks))

    states = [
        estimate_gesture_state(_three_finger_landmarks(offset), tracker=tracker)
        for offset in (0.0, 0.06, 0.12, 0.18)
    ]

    assert states[-1]["action"] == "scroll_down"
    assert states[-1]["gesture_name"].startswith("Three Finger Scroll")


def test_tracker_reset_clears_scroll_cooldown():
    tracker = GestureTracker()
    tracker.last_scroll_time = 123.0
    tracker.last_zoom_time = 124.0
    tracker.two_hand_distance_history.append((0.5, 125.0))
    tracker.reset()
    assert tracker.last_scroll_time == 0.0
    assert tracker.last_zoom_time == 0.0
    assert tracker.two_hand_distance_history == []


def _two_hands_at_distance(distance: float):
    left = [(0.25, 0.5, 0.0)] * 21
    right = [(0.75, 0.5, 0.0)] * 21
    left[0] = (0.4 - distance / 2, 0.5, 0.0)
    left[9] = (0.4 - distance / 2, 0.5, 0.0)
    right[0] = (0.4 + distance / 2, 0.5, 0.0)
    right[9] = (0.4 + distance / 2, 0.5, 0.0)
    return [left, right]


def test_two_hand_spread_triggers_browser_zoom_in(monkeypatch):
    from gesture_utils import estimate_two_hand_zoom

    tracker = GestureTracker()
    ticks = iter([2.00, 2.05, 2.10, 2.15])
    monkeypatch.setattr("gesture_utils.time.monotonic", lambda: next(ticks))
    actions = [
        estimate_two_hand_zoom(_two_hands_at_distance(distance), tracker)
        for distance in (0.20, 0.25, 0.32, 0.40)
    ]
    assert "zoom_in" in actions


def test_two_hand_zoom_requires_two_hands_and_resets_history():
    from gesture_utils import estimate_two_hand_zoom

    tracker = GestureTracker()
    tracker.two_hand_distance_history.append((0.5, 1.0))
    assert estimate_two_hand_zoom([_two_hands_at_distance(0.4)[0]], tracker) is None
    assert tracker.two_hand_distance_history == []


def test_two_hand_close_triggers_browser_zoom_out(monkeypatch):
    from gesture_utils import estimate_two_hand_zoom

    tracker = GestureTracker()
    ticks = iter([3.00, 3.05, 3.10, 3.15])
    monkeypatch.setattr("gesture_utils.time.monotonic", lambda: next(ticks))
    actions = [
        estimate_two_hand_zoom(_two_hands_at_distance(distance), tracker)
        for distance in (0.42, 0.35, 0.27, 0.18)
    ]
    assert "zoom_out" in actions


def test_cursor_coordinates_match_mirrored_camera_preview_by_default():
    assert orient_cursor_for_display((0.2, 0.7)) == (0.2, 0.7)


def test_cursor_axis_inversion_is_explicit_and_independent():
    assert orient_cursor_for_display((0.2, 0.7), invert_x=True) == (0.8, 0.7)
    assert orient_cursor_for_display((0.2, 0.7), invert_y=True) == (0.2, 0.30000000000000004)
