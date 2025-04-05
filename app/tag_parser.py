# app/tag_parser.py
import re
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional


class Tag:
    def __init__(self, name: str, start_position: Optional[int] = None):
        self.name = name
        self.start_positions = [start_position] if start_position is not None else []
        self.end_positions = []
        self.pairs = []

        # New attributes for categorized tag content
        self.main_topics = []
        self.subject_info = []

        # Process tag name to extract main topics and subject/information
        self._process_tag_content()

    def _process_tag_content(self):
        """Parse tag name to extract main topics (no spaces) and subject/information (with spaces)"""
        if not self.name:
            return

        # Split tag content by semicolon
        parts = self.name.split(";")
        parts = [part.strip() for part in parts if part.strip()]

        # If there's only one item, it's a main topic regardless of spaces
        if len(parts) == 1:
            self.main_topics.append(parts[0])
            return

        # For multiple items, first categorize according to spaces
        for part in parts:
            # If part contains no spaces, it's a main topic
            if " " not in part:
                self.main_topics.append(part)
            else:
                # If part contains spaces, it's subject/information
                self.subject_info.append(part)

        # If we have no subject_info items but multiple main_topics,
        # move the last main_topic to subject_info
        if len(self.main_topics) > 1 and not self.subject_info:
            self.subject_info.append(self.main_topics.pop())

    def add_start_position(self, position: int):
        self.start_positions.append(position)

    def add_end_position(self, position: int):
        self.end_positions.append(position)

    def create_pairs(self):
        """Match start and end positions to create pairs."""
        # Sort positions to ensure correct pairing
        start_sorted = sorted(self.start_positions)
        end_sorted = sorted(self.end_positions)

        # Only pair matching numbers of opening and closing tags
        pair_count = min(len(start_sorted), len(end_sorted))
        self.pairs = [(start_sorted[i], end_sorted[i]) for i in range(pair_count)]

    def to_dict(self):
        return {
            "name": self.name,
            "start_positions": self.start_positions,
            "end_positions": self.end_positions,
            "pairs": self.pairs,
            "main_topics": self.main_topics,
            "subject_info": self.subject_info,
        }


class DocumentTags:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)

        # Read file content
        with open(file_path, "r", encoding="utf-8") as f:
            self.content = f.read()

        # Initialize tag collections
        self.tags = []  # List of Tag objects
        self.opening_errors = []  # Tags with opening but no closing
        self.closing_errors = []  # Tags with closing but no opening

        # Process the document
        self._find_tags()
        self._match_tags()
        self._identify_errors()

    def _find_tag_by_name(self, tag_name: str) -> Optional[Tag]:
        """Find a tag by name in the tags list."""
        for tag in self.tags:
            if tag.name == tag_name:
                return tag
        return None

    def _find_tags(self):
        """Find all opening and closing tags in the document."""
        # Find opening tags - matches anything like <tag> or <tag;info>
        opening_pattern = r"<([^/][^>]*)>"
        for match in re.finditer(opening_pattern, self.content):
            tag_name = match.group(1).strip()
            start_position = match.end()

            # Find existing tag or create new one
            tag = self._find_tag_by_name(tag_name)
            if tag is None:
                tag = Tag(tag_name, start_position)
                self.tags.append(tag)
            else:
                tag.add_start_position(start_position)

        # Find closing tags - matches anything like </tag> or </tag;info>
        closing_pattern = r"</([^>]*)>"
        for match in re.finditer(closing_pattern, self.content):
            tag_name = match.group(1).strip()
            end_position = match.start()

            # Find existing tag or create new one
            tag = self._find_tag_by_name(tag_name)
            if tag is None:
                tag = Tag(tag_name)
                self.tags.append(tag)

            tag.add_end_position(end_position)

    def _match_tags(self):
        """Match opening and closing tags to create pairs."""
        for tag in self.tags:
            tag.create_pairs()

    def _identify_errors(self):
        """Identify tags with errors (unmatched opening or closing)."""
        self.opening_errors = []
        self.closing_errors = []

        for tag in self.tags:
            if len(tag.start_positions) > len(tag.end_positions):
                self.opening_errors.append(tag.name)
            elif len(tag.start_positions) < len(tag.end_positions):
                self.closing_errors.append(tag.name)

    def save_metadata(self, output_dir: str = None):
        """Save tag metadata to a JSON file."""
        if output_dir is None:
            output_dir = os.path.dirname(self.file_path)

        base_name = os.path.splitext(self.file_name)[0]
        output_path = os.path.join(output_dir, f"{base_name}_tags.json")

        # Generate organized tag structure
        organized_tags = self._generate_organized_tags()

        metadata = {
            "file_name": self.file_name,
            "file_path": self.file_path,
            "tags": [tag.to_dict() for tag in self.tags],
            "opening_errors": self.opening_errors,
            "closing_errors": self.closing_errors,
            "organized_tags": organized_tags,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return output_path

    def _generate_organized_tags(self):
        """Generate a hierarchical organization of tags grouped by main topics."""
        organized = {}

        # Only process tags without errors
        valid_tags = [
            tag
            for tag in self.tags
            if tag.name not in self.opening_errors
            and tag.name not in self.closing_errors
        ]

        for tag in valid_tags:
            # Skip tags with no main topics
            if not tag.main_topics:
                continue

            # Get the first main topic as the primary category
            main_topic = tag.main_topics[0]

            # Initialize the main topic if not present
            if main_topic not in organized:
                organized[main_topic] = []

            # Create entry for this tag instance
            tag_entry = {
                "full_tag": tag.name,
                "subject_info": tag.subject_info,
                "remaining_main_topics": (
                    tag.main_topics[1:] if len(tag.main_topics) > 1 else []
                ),
                "start_positions": tag.start_positions,
                "end_positions": tag.end_positions,
                "pairs": tag.pairs,
            }

            organized[main_topic].append(tag_entry)

        return organized
