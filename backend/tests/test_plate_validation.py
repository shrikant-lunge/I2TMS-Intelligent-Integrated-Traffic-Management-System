"""
Tests for Plate Validation and OCR normalization.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.ocr_service import normalize_plate_text, validate_indian_plate


class TestPlateNormalization:
    """Test plate text normalization."""

    def test_basic_normalization(self):
        assert normalize_plate_text("MH 12 AB 1234") == "MH12AB1234"

    def test_lowercase(self):
        assert normalize_plate_text("mh12ab1234") == "MH12AB1234"

    def test_special_characters(self):
        assert normalize_plate_text("MH-12-AB-1234") == "MH12AB1234"

    def test_spaces_and_dots(self):
        assert normalize_plate_text("MH.12.AB.1234") == "MH12AB1234"

    def test_empty_string(self):
        assert normalize_plate_text("") == ""


class TestPlateValidation:
    """Test Indian plate format validation."""

    def test_reject_short_ocr_noise(self):
        assert validate_indian_plate("FE32") == False
        assert validate_indian_plate("A1") == False
        assert validate_indian_plate("0") == False

    def test_valid_standard_format(self):
        assert validate_indian_plate("MH12AB1234") == True

    def test_valid_two_letter_series(self):
        assert validate_indian_plate("MH12AB1234") == True

    def test_valid_single_letter_series(self):
        assert validate_indian_plate("MH12A1234") == True

    def test_reject_too_short(self):
        assert validate_indian_plate("ABC") == False

    def test_reject_only_digits(self):
        assert validate_indian_plate("123456") == False

    def test_reject_only_letters(self):
        assert validate_indian_plate("ABCDEF") == False

    def test_reject_empty(self):
        assert validate_indian_plate("") == False

    def test_reject_random_text(self):
        assert validate_indian_plate("RANDOMTEXT") == False

    def test_reject_none(self):
        assert validate_indian_plate(None) == False

    def test_valid_karnataka(self):
        assert validate_indian_plate("KA01AB1234") == True

    def test_valid_delhi(self):
        assert validate_indian_plate("DL01AB1234") == True

    def test_reject_invalid_start(self):
        # Generalized plate validation allows alphanumeric formats; this case is only invalid for Indian-specific format.
        assert validate_indian_plate("12AB1234") == False
