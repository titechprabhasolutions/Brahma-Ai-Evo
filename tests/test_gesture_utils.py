from gesture_utils import GestureTracker, estimate_gesture_state


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
