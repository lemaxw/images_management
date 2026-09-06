from unittest import TestCase, main
from unittest.mock import patch

import tale_preparation


class LocationFromTagsTest(TestCase):
    def test_jerusalim_is_inferred_by_ollama_not_known_tags(self):
        with patch("tale_preparation.call_ollama", return_value="Jerusalem, Israel") as call_ollama:
            location = tale_preparation.generate_location_from_tags(
                "Jerusalim; Landscape; israel; Jerusalim; Landscape; israel"
            )

        self.assertEqual(location, "Jerusalem, Israel")
        call_ollama.assert_called_once()
        prompt = call_ollama.call_args.args[0]
        self.assertIn("misspellings", prompt)
        self.assertIn("transliterations", prompt)

    def test_prompt_makes_tags_primary_over_caption(self):
        caption = (
            "The image shows a busy workbench with electronic devices and tangled wires, "
            "indicating an indoor workshop or lab setting."
        )
        with patch("tale_preparation.call_ollama", return_value="Tel Aviv, Israel") as call_ollama:
            location = tale_preparation.generate_location_from_tags(
                "israel; koncert; street; tel-aviv; israel; koncert; street; tel-aviv",
                caption,
            )

        self.assertEqual(location, "Tel Aviv, Israel")
        prompt = call_ollama.call_args.args[0]
        self.assertIn("metadata tags are the primary evidence", prompt)
        self.assertIn("must not override explicit place or country tags", prompt)

    def test_region_is_accepted_as_a_location(self):
        with patch("tale_preparation.call_ollama", return_value="Khevsureti, Georgia") as call_ollama:
            location = tale_preparation.generate_location_from_tags(
                "Georgia; Khevsuretia; Landscape"
            )

        self.assertEqual(location, "Khevsureti, Georgia")
        prompt = call_ollama.call_args.args[0]
        self.assertIn("region", prompt)
        self.assertIn("Place, Country", prompt)
        self.assertNotIn("plausible city and country", prompt)

    def test_parse_location_after_think_block(self):
        raw = "<think>\nJerusalim means Jerusalem.\n</think>\nJerusalem, Israel"

        self.assertEqual(tale_preparation._parse_location_response(raw), "Jerusalem, Israel")

    def test_parse_json_location_response(self):
        raw = '{"city": "Jerusalem", "country": "Israel"}'

        self.assertEqual(tale_preparation._parse_location_response(raw), "Jerusalem, Israel")

    def test_parse_region_label_response(self):
        raw = "Region: Khevsureti\nCountry: Georgia"

        self.assertEqual(tale_preparation._parse_location_response(raw), "Khevsureti, Georgia")

    def test_parse_explanatory_location_response(self):
        raw = "The most likely location is Jerusalem, Israel."

        self.assertEqual(tale_preparation._parse_location_response(raw), "Jerusalem, Israel")


if __name__ == "__main__":
    main()
