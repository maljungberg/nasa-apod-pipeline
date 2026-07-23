"""
Unit tests for pipeline.transform
"""

import html
import pytest
from pipeline.transform import clean_copyright, clean_explanation, clean_record, transform_all


# -----------------------------------------------
# Tests for clean_copyright
# -----------------------------------------------

class TestCleanCopyright:
    def test_none(self):
        assert clean_copyright(None) == ""

    def test_empty_string(self):
        assert clean_copyright("") == ""

    def test_public_domain(self):
        assert clean_copyright("Public Domain") == "Public Domain"

    def test_simple_name(self):
        assert clean_copyright("John Doe") == "John Doe"

    def test_with_newlines(self):
        raw = "Tunç Tezel (TWAN)\n\nText:\nKeighley Rockcliffe  \n(NASA\nGSFC, \nUMBC CSST, \nCRESST II)"
        result = clean_copyright(raw)
        # Must cut at \n\nText: and remove any spaces
        assert result == "Tunç Tezel (TWAN)"
        # It must not contain "Text:" or "Keighley"
        assert "Text:" not in result
        assert "Keighley" not in result

    def test_multiple_spaces_and_newlines(self):
        raw = "  Some\n  Artist  \n\n"
        result = clean_copyright(raw)
        assert result == "Some Artist"

    def test_only_text_section(self):
        raw = "\n\nText:\nJohn Smith"
        result = clean_copyright(raw)
        assert result == "John Smith"


# -----------------------------------------------
# Tests for clean_explanation
# -----------------------------------------------

class TestCleanExplanation:
    def test_unescape_html_entities(self):
        raw = "The &amp; symbol &amp; more &lt;test&gt;"
        result = clean_explanation(raw)
        assert "&" in result
        assert "&amp;" not in result
        # <test> is removed because the function deletes HTML tags
        assert "The & symbol & more" in result
        assert "<test>" not in result   # consistency with the aim of cleaning

    def test_br_tags_replaced(self):
        raw = "Line 1<br>Line 2<br/>Line 3"
        result = clean_explanation(raw)
        assert "\n" in result
        assert "<br>" not in result
        assert "Line 1\nLine 2\nLine 3" == result

    def test_p_tags_replaced(self):
        raw = "<p>Paragraph 1</p><p>Paragraph 2</p>"
        result = clean_explanation(raw)
        assert "<p>" not in result
        assert "Paragraph 1\n\nParagraph 2" in result

    def test_other_tags_removed(self):
        raw = '<a href="http://example.com">link</a> <b>bold</b>'
        result = clean_explanation(raw)
        assert "link" in result
        assert "bold" in result
        assert "<a" not in result
        assert "<b>" not in result

    def test_multiple_linebreaks_collapsed(self):
        raw = "Paragraph one\n\n\n\nParagraph two"
        result = clean_explanation(raw)
        # Must have only one line break between paragraphs (i.e., an empty line)
        assert "Paragraph one\n\nParagraph two" == result

    def test_tabs_and_multiple_spaces(self):
        raw = "Some   text\t\twith tabs"
        result = clean_explanation(raw)
        assert result == "Some text with tabs"


# -----------------------------------------------
# Tests for clean_record
# -----------------------------------------------

class TestCleanRecord:
    def test_image_record(self):
        raw = {
            "date": "2026-06-28",
            "title": "  Test Title  ",
            "explanation": "This is a <b>test</b> &amp; example.",
            "url": "http://example.com/image.jpg",
            "hdurl": "http://example.com/image_hd.jpg",
            "media_type": "image",
            "copyright": "John Doe",
            "service_version": "v1"
        }
        cleaned = clean_record(raw)
        assert cleaned["date"] == "2026-06-28"
        assert cleaned["title"] == "Test Title"
        assert "&" in cleaned["explanation"]
        assert "&amp;" not in cleaned["explanation"]
        assert cleaned["url"] == "http://example.com/image.jpg"
        assert cleaned["hdurl"] == "http://example.com/image_hd.jpg"
        assert cleaned["media_type"] == "image"
        assert cleaned["copyright"] == "John Doe"
        assert cleaned["thumbnail_url"] == ""  # no thumbnail for images
        assert "load_timestamp" in cleaned
        assert "service_version" not in cleaned  # not included in cleaned record

    def test_video_record_with_thumbnail(self):
        raw = {
            "date": "2026-06-27",
            "title": "Test Video",
            "explanation": "Video explanation.",
            "url": "http://youtube.com/watch?v=123",
            "media_type": "video",
            "thumbnail_url": "http://img.youtube.com/vi/123/0.jpg"
        }
        cleaned = clean_record(raw)
        assert cleaned["media_type"] == "video"
        assert cleaned["thumbnail_url"] == "http://img.youtube.com/vi/123/0.jpg"
        assert cleaned["hdurl"] == ""  # no hdurl

    def test_missing_copyright(self):
        raw = {
            "date": "2026-06-26",
            "title": "No copyright",
            "explanation": "Explanation.",
            "url": "http://example.com/img.jpg"
        }
        cleaned = clean_record(raw)
        assert cleaned["copyright"] == ""

    def test_missing_hdurl(self):
        raw = {
            "date": "2026-06-26",
            "title": "No HD",
            "explanation": "Explanation.",
            "url": "http://example.com/img.jpg"
        }
        cleaned = clean_record(raw)
        assert cleaned["hdurl"] == ""


# -----------------------------------------------
# Tests for transform_all
# -----------------------------------------------

class TestTransformAll:
    def test_empty_list(self):
        assert transform_all([]) == []

    def test_record_without_date_is_skipped(self):
        records = [
            {"title": "No date", "url": "x"},
            {"date": "2026-06-28", "title": "Good", "url": "y"}
        ]
        cleaned = transform_all(records)
        assert len(cleaned) == 1
        assert cleaned[0]["date"] == "2026-06-28"

    def test_all_valid(self):
        records = [
            {"date": "2026-06-28", "title": "A", "url": "x"},
            {"date": "2026-06-27", "title": "B", "url": "y"}
        ]
        cleaned = transform_all(records)
        assert len(cleaned) == 2
        assert all("load_timestamp" in r for r in cleaned)
        