from unittest import TestCase, main
from pathlib import Path
from unittest.mock import patch

import publish_best_poem


class SelectPoemExcerptTest(TestCase):
    def test_rejects_entity_when_ollama_does_not_copy_poem_lines(self):
        poem = {
            "text": "Сховалось равликом місто.\nСіче його дощ, січе.\nВ під’їздах будов — тісно.",
            "entity": "City hidden in rain, chains close entrances",
        }
        with patch("publish_best_poem.call_ollama", return_value=poem["entity"]):
            excerpt = publish_best_poem.select_poem_excerpt(
                poem,
                "workbench with tangled wires",
                "israel; koncert; street; tel-aviv",
                "Tel Aviv, Israel",
            )

        self.assertNotIn(poem["entity"], excerpt)
        self.assertIn("Сховалось равликом місто.", excerpt)
        self.assertIn("Січе його дощ, січе.", excerpt)

    def test_formats_non_contiguous_original_lines_with_ellipses(self):
        poem_text = "\n".join(
            [
                "Сховалось равликом місто.",
                "Січе його дощ, січе.",
                "В під’їздах будов — тісно.",
                "Набої через плече.",
                "З-під мурів — повів гниття.",
            ]
        )
        excerpt = "\n".join(
            [
                "Січе його дощ, січе.",
                "В під’їздах будов — тісно.",
                "З-під мурів — повів гниття.",
            ]
        )

        self.assertEqual(
            publish_best_poem._format_excerpt_with_context(poem_text, excerpt),
            "\n".join(
                [
                    "...",
                    "Січе його дощ, січе.",
                    "В під’їздах будов — тісно.",
                    "...",
                    "З-під мурів — повів гниття.",
                ]
            ),
        )

    def test_batch_excerpt_selection_validates_each_poem(self):
        poems = [
            {"id": "one", "entity": "rain", "text": "First one\nSecond one\nThird one\nFourth one"},
            {"id": "two", "entity": "sun", "text": "First two\nSecond two\nThird two"},
        ]
        response = '{"one": ["Second one", "Fourth one"], "two": ["invented line"]}'

        with patch("publish_best_poem.call_ollama", return_value=response) as call:
            excerpts = publish_best_poem.select_poem_excerpts(
                poems, "a landscape", "rain; sun", "Somewhere"
            )

        call.assert_called_once()
        self.assertEqual(excerpts["one"], "...\nSecond one\n...\nFourth one")
        self.assertEqual(excerpts["two"], "First two\nSecond two\nThird two")


class SelectTopPoemTest(TestCase):
    def test_scores_generated_tales_in_batches(self):
        class FakeMatcher:
            def __init__(self):
                self.batch_sizes = []

            def score(self, _text):
                return [0.8, 0.7]

            def score_many(self, texts):
                self.batch_sizes.append(len(texts))
                return [[0.9, 0.1] if "rain" in text else [0.1, 0.9] for text in texts]

        poems = [
            {"id": "one", "entity": "rain", "rating": 1},
            {"id": "two", "entity": "sun", "rating": 1},
        ]
        matcher = FakeMatcher()
        responses = [
            "rain over stone\nsun over water",
            "rain in a valley\nsun in a field",
            "rain becomes a river\nsun becomes a star",
        ]
        environment = {
            "PUBLISH_INITIAL_LOOPS": "2",
            "PUBLISH_IMPROVEMENT_LOOPS": "1",
            "PUBLISH_TOP_SIZE": "2",
        }

        with patch.dict("os.environ", environment), patch(
            "publish_best_poem.call_ollama", side_effect=responses
        ) as call:
            selected = publish_best_poem.select_top_poem_ids(
                "Somewhere",
                "rain and sun",
                poems,
                target_poems=poems,
                entity_matcher=matcher,
            )

        self.assertEqual(call.call_count, 3)
        self.assertEqual(matcher.batch_sizes, [2, 2, 2])
        self.assertEqual({poem["id"] for poem in selected}, {"one", "two"})

    def test_recent_first_place_poem_can_only_appear_below_first(self):
        class FakeMatcher:
            def score(self, _text):
                return [0.9, 0.8, 0.7]

            def score_many(self, _texts):
                return []

        poems = [
            {"id": "recent", "entity": "rain", "rating": 1},
            {"id": "eligible", "entity": "sun", "rating": 1},
            {"id": "third", "entity": "wind", "rating": 1},
        ]
        environment = {
            "PUBLISH_INITIAL_LOOPS": "0",
            "PUBLISH_IMPROVEMENT_LOOPS": "0",
            "PUBLISH_TOP_SIZE": "3",
        }

        with patch.dict("os.environ", environment):
            selected = publish_best_poem.select_top_poem_ids(
                "Somewhere",
                "rain and sun",
                poems,
                target_poems=poems,
                entity_matcher=FakeMatcher(),
                excluded_first_ids={"recent"},
            )

        self.assertEqual([poem["id"] for poem in selected], ["eligible", "recent", "third"])


class FirstPlaceRecordingTest(TestCase):
    def test_records_only_first_poem_after_successful_publication(self):
        poems = [
            {"id": "first", "entity": "rain", "text": "First poem"},
            {"id": "second", "entity": "sun", "text": "Second poem"},
        ]
        config = {
            "lang": "en",
            "label": "English",
            "poems": poems,
            "location": lambda location: location,
            "word_link": "Full poem",
        }
        selected = [
            {"id": "first", "generated_tale_score": 0.9, "image_score": 0.8},
            {"id": "second", "generated_tale_score": 0.8, "image_score": 0.7},
        ]

        with patch.dict("os.environ", {"PUBLISH_TIMING": "0"}), patch(
            "publish_best_poem._language_configs", return_value=[config]
        ), patch("publish_best_poem.SentenceMatcher"), patch(
            "publish_best_poem.get_recent_first_place_ids", return_value=set()
        ), patch(
            "publish_best_poem._iter_image_paths", return_value=[Path("photo.jpg")]
        ), patch(
            "publish_best_poem.get_caption_backend"
        ), patch(
            "publish_best_poem.caption_image", return_value="caption"
        ), patch(
            "publish_best_poem.get_xmp_tags", return_value="tags"
        ), patch(
            "publish_best_poem.get_gps_coords", return_value=None
        ), patch(
            "publish_best_poem.generate_location_from_tags", return_value="Place, Country"
        ), patch(
            "publish_best_poem.select_top_poem_ids", return_value=selected
        ), patch(
            "publish_best_poem.select_poem_excerpts",
            return_value={"first": "First poem", "second": "Second poem"},
        ), patch(
            "publish_best_poem.publish_poem", return_value=True
        ), patch(
            "publish_best_poem.record_first_place"
        ) as record:
            publish_best_poem.process_directory("unused", just_print=False)

        record.assert_called_once_with("first", "en")


if __name__ == "__main__":
    main()
