from __future__ import annotations


class Recommender:
    def recommend(self, sessions: list[dict], bigrams: list[str]) -> str:
        if not sessions:
            return "No sessions yet — start your first lesson to begin tracking progress!"

        avg_accuracy = sum(s["accuracy"] for s in sessions) / len(sessions)
        wpms = [s["wpm"] for s in sessions]

        if avg_accuracy < 90.0:
            return (
                f"Your average accuracy is {avg_accuracy:.1f}% — below 90%. "
                "Try enabling Strict Mode to force yourself to fix every error before continuing."
            )

        if len(wpms) >= 7:
            oldest, newest = wpms[0], wpms[-1]
            if oldest > 0 and (newest - oldest) / oldest < 0.05:
                if bigrams:
                    bg_list = ", ".join(f"'{b}'" for b in bigrams[:3])
                    return (
                        f"Your WPM has plateaued. You're making frequent errors on {bg_list}. "
                        "Try a focused words session — these bigrams will appear more often."
                    )
                return (
                    "Your WPM has plateaued. Mix in code or sentence sessions "
                    "to challenge different finger patterns."
                )

        by_type: dict[str, list[float]] = {}
        for s in sessions:
            by_type.setdefault(s["content_type"], []).append(s["wpm"])
        if len(by_type) > 1:
            avg_by_type = {t: sum(v) / len(v) for t, v in by_type.items()}
            slowest = min(avg_by_type, key=avg_by_type.get)
            fastest = max(avg_by_type, key=avg_by_type.get)
            if avg_by_type[fastest] - avg_by_type[slowest] > 15:
                return (
                    f"You're significantly slower on '{slowest}' content "
                    f"({avg_by_type[slowest]:.0f} WPM vs {avg_by_type[fastest]:.0f} WPM on '{fastest}'). "
                    f"More '{slowest}' practice will close the gap."
                )

        latest_wpm = wpms[-1]
        return f"Great work! You hit {latest_wpm:.0f} WPM last session. Keep the streak going!"
