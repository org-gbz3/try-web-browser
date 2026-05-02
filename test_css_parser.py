import sys
import unittest

from browser.main import CSSParser, DescendantSelector, Element, Tagselector

sys.path.insert(0, '/workspaces/try-web-browser')

# CSSParser クラスの各メソッドの単体テストと、parse() メソッドの統合テストを含むテストケースを定義
# $ python -m unittest test_css_parser.py -v


class TestCSSParserWhitespace(unittest.TestCase):
    """whitespace() メソッドのテスト"""

    def test_empty_string(self):
        parser = CSSParser("")
        parser.whitespace()
        self.assertEqual(parser.i, 0)

    def test_no_whitespace(self):
        parser = CSSParser("hello")
        parser.whitespace()
        self.assertEqual(parser.i, 0)

    def test_single_space(self):
        parser = CSSParser(" hello")
        parser.whitespace()
        self.assertEqual(parser.i, 1)

    def test_multiple_spaces(self):
        parser = CSSParser("   hello")
        parser.whitespace()
        self.assertEqual(parser.i, 3)

    def test_tabs_and_newlines(self):
        parser = CSSParser("\t\n  hello")
        parser.whitespace()
        self.assertEqual(parser.i, 4)

    def test_all_whitespace(self):
        s = "   \t\n  "
        parser = CSSParser(s)
        parser.whitespace()
        self.assertEqual(parser.i, len(s))


class TestCSSParserWord(unittest.TestCase):
    """word() メソッドのテスト"""

    def test_simple_word(self):
        parser = CSSParser("color")
        word = parser.word()
        self.assertEqual(word, "color")
        self.assertEqual(parser.i, 5)

    def test_word_with_numbers(self):
        parser = CSSParser("color123")
        word = parser.word()
        self.assertEqual(word, "color123")

    def test_word_with_hyphen(self):
        parser = CSSParser("background-color")
        word = parser.word()
        self.assertEqual(word, "background-color")

    def test_word_with_percent(self):
        parser = CSSParser("50%")
        word = parser.word()
        self.assertEqual(word, "50%")

    def test_word_with_hash(self):
        parser = CSSParser("#ff0000")
        word = parser.word()
        self.assertEqual(word, "#ff0000")

    def test_word_with_dot(self):
        parser = CSSParser("1.5px")
        word = parser.word()
        self.assertEqual(word, "1.5px")

    def test_word_stops_at_space(self):
        parser = CSSParser("color red")
        word = parser.word()
        self.assertEqual(word, "color")
        self.assertEqual(parser.i, 5)

    def test_word_stops_at_colon(self):
        parser = CSSParser("color:red")
        word = parser.word()
        self.assertEqual(word, "color")
        self.assertEqual(parser.i, 5)

    def test_word_stops_at_semicolon(self):
        parser = CSSParser("color;")
        word = parser.word()
        self.assertEqual(word, "color")
        self.assertEqual(parser.i, 5)

    def test_word_stops_at_brace(self):
        parser = CSSParser("div{")
        word = parser.word()
        self.assertEqual(word, "div")

    def test_empty_word_raises_exception(self):
        parser = CSSParser("")
        with self.assertRaises(Exception) as context:
            parser.word()
        self.assertIn("expected word", str(context.exception))

    def test_word_at_special_char_raises_exception(self):
        parser = CSSParser(":color")
        with self.assertRaises(Exception):
            parser.word()


class TestCSSParserLiteral(unittest.TestCase):
    """literal() メソッドのテスト"""

    def test_matching_literal(self):
        parser = CSSParser(":")
        parser.literal(":")
        self.assertEqual(parser.i, 1)

    def test_matching_brace(self):
        parser = CSSParser("{")
        parser.literal("{")
        self.assertEqual(parser.i, 1)

    def test_closing_brace(self):
        parser = CSSParser("}")
        parser.literal("}")
        self.assertEqual(parser.i, 1)

    def test_semicolon(self):
        parser = CSSParser(";")
        parser.literal(";")
        self.assertEqual(parser.i, 1)

    def test_mismatched_literal(self):
        parser = CSSParser(":")
        with self.assertRaises(Exception) as context:
            parser.literal("{")
        self.assertIn("expected", str(context.exception))

    def test_empty_string_raises_exception(self):
        parser = CSSParser("")
        with self.assertRaises(Exception):
            parser.literal(":")


class TestCSSParserPair(unittest.TestCase):
    """pair() メソッドのテスト"""

    def test_simple_pair(self):
        parser = CSSParser("color: red;")
        prop, val = parser.pair()
        self.assertEqual(prop, "color")
        self.assertEqual(val, "red")

    def test_pair_with_multiple_spaces(self):
        parser = CSSParser("color  :  red")
        prop, val = parser.pair()
        self.assertEqual(prop, "color")
        self.assertEqual(val, "red")

    def test_pair_property_case_insensitive(self):
        # プロパティは lowercase に、値は保持
        parser = CSSParser("Color: Red")
        prop, val = parser.pair()
        self.assertEqual(prop, "color")
        self.assertEqual(val, "Red")

    def test_pair_with_hyphenated_property(self):
        parser = CSSParser("background-color: blue")
        prop, val = parser.pair()
        self.assertEqual(prop, "background-color")
        self.assertEqual(val, "blue")

    def test_pair_with_number_value(self):
        parser = CSSParser("fontsize: 12")
        prop, val = parser.pair()
        self.assertEqual(prop, "fontsize")
        self.assertEqual(val, "12")

    def test_pair_with_percent_value(self):
        parser = CSSParser("width: 50%")
        prop, val = parser.pair()
        self.assertEqual(prop, "width")
        self.assertEqual(val, "50%")

    def test_pair_with_hex_color(self):
        parser = CSSParser("color: #ff0000")
        prop, val = parser.pair()
        self.assertEqual(prop, "color")
        self.assertEqual(val, "#ff0000")

    def test_missing_colon_raises_exception(self):
        parser = CSSParser("color red")
        with self.assertRaises(Exception):
            parser.pair()

    def test_missing_value_raises_exception(self):
        parser = CSSParser("color:")
        with self.assertRaises(Exception):
            parser.pair()


class TestCSSParserBody(unittest.TestCase):
    """body() メソッドのテスト"""

    def test_empty_body(self):
        parser = CSSParser("}")
        pairs = parser.body()
        self.assertEqual(pairs, {})

    def test_single_property(self):
        parser = CSSParser("color: red;}")
        pairs = parser.body()
        self.assertEqual(pairs, {"color": "red"})

    def test_multiple_properties(self):
        parser = CSSParser("color: red; background: blue;}")
        pairs = parser.body()
        self.assertEqual(pairs, {"color": "red", "background": "blue"})

    def test_multiple_properties_with_whitespace(self):
        parser = CSSParser("color: red;  background: blue;  fontsize: 12;}")
        pairs = parser.body()
        self.assertEqual(
            pairs, {"color": "red", "background": "blue", "fontsize": "12"})

    def test_body_property_lowercase_value_preserved(self):
        parser = CSSParser("Color: Red; Background: Blue;}")
        pairs = parser.body()
        self.assertEqual(pairs, {"color": "Red", "background": "Blue"})

    def test_body_stops_at_closing_brace(self):
        parser = CSSParser("color: red;}")
        pairs = parser.body()
        self.assertEqual(parser.s[parser.i], "}")

    def test_body_with_invalid_property_skips(self):
        # invalid property は ignore_until で ; まで飛ばされる
        parser = CSSParser("color: red; invalid; background: blue;}")
        pairs = parser.body()
        self.assertIn("color", pairs)
        self.assertIn("background", pairs)
        self.assertEqual(pairs["color"], "red")
        self.assertEqual(pairs["background"], "blue")

    def test_duplicate_properties_later_value_wins(self):
        parser = CSSParser("color: red; color: blue;}")
        pairs = parser.body()
        self.assertEqual(pairs["color"], "blue")

    def test_body_without_closing_brace(self):
        parser = CSSParser("color: red;")
        pairs = parser.body()
        # Closing brace がなくても読み込みを終わる
        self.assertEqual(pairs["color"], "red")


class TestCSSParserIgnoreUntil(unittest.TestCase):
    """ignore_until() メソッドのテスト"""

    def test_ignore_until_semicolon(self):
        parser = CSSParser("garbage text;}")
        result = parser.ignore_until([";", "}"])
        self.assertEqual(result, ";")
        self.assertEqual(parser.i, 12)

    def test_ignore_until_brace(self):
        parser = CSSParser("garbage text}")
        result = parser.ignore_until([";", "}"])
        self.assertEqual(result, "}")
        self.assertEqual(parser.i, 12)

    def test_ignore_until_end_of_string(self):
        parser = CSSParser("garbage text")
        result = parser.ignore_until([";", "}"])
        self.assertIsNone(result)
        self.assertEqual(parser.i, 12)

    def test_ignore_until_empty_chars(self):
        parser = CSSParser("text")
        result = parser.ignore_until([])
        self.assertIsNone(result)


class TestCSSParserSelector(unittest.TestCase):
    """selector() メソッドのテスト"""

    def test_simple_selector(self):
        parser = CSSParser("div{")
        selector = parser.selector()
        self.assertIsInstance(selector, Tagselector)
        self.assertEqual(selector.tag, "div")

    def test_selector_case_insensitive(self):
        parser = CSSParser("DIV{")
        selector = parser.selector()
        self.assertEqual(selector.tag, "div")

    def test_descendant_selector(self):
        parser = CSSParser("div p{")
        selector = parser.selector()
        self.assertIsInstance(selector, DescendantSelector)
        self.assertEqual(selector.descendant.tag, "p")
        self.assertEqual(selector.anncestor.tag, "div")

    def test_three_level_descendant_selector(self):
        parser = CSSParser("html body p{")
        selector = parser.selector()
        # 最も深い descendant は p
        self.assertEqual(selector.descendant.tag, "p")
        # anncestor は body
        self.assertEqual(selector.anncestor.descendant.tag, "body")
        # さらにその anncestor は html
        self.assertEqual(selector.anncestor.anncestor.tag, "html")

    def test_selector_with_whitespace(self):
        parser = CSSParser("div  p  {")
        selector = parser.selector()
        self.assertEqual(selector.descendant.tag, "p")


class TestTagselector(unittest.TestCase):
    """Tagselector クラスのテスト"""

    def test_matches_element(self):
        selector = Tagselector("div")
        element = Element("div", {}, None)
        self.assertTrue(selector.matches(element))

    def test_not_matches_different_tag(self):
        selector = Tagselector("div")
        element = Element("p", {}, None)
        self.assertFalse(selector.matches(element))

    def test_case_sensitive_match(self):
        selector = Tagselector("div")
        element = Element("DIV", {}, None)
        self.assertFalse(selector.matches(element))

    def test_not_matches_text_node(self):
        from browser.main import Text
        selector = Tagselector("div")
        text_node = Text("hello", None)
        self.assertFalse(selector.matches(text_node))


class TestDescendantSelector(unittest.TestCase):
    """DescendantSelector クラスのテスト"""

    def test_matches_direct_child(self):
        parent = Element("div", {}, None)
        child = Element("p", {}, parent)
        parent.children.append(child)

        ancestor_sel = Tagselector("div")
        descendant_sel = Tagselector("p")
        selector = DescendantSelector(ancestor_sel, descendant_sel)

        self.assertTrue(selector.matches(child))

    def test_matches_grandchild(self):
        root = Element("div", {}, None)
        parent = Element("body", {}, root)
        child = Element("p", {}, parent)

        root.children.append(parent)
        parent.children.append(child)

        ancestor_sel = Tagselector("div")
        descendant_sel = Tagselector("p")
        selector = DescendantSelector(ancestor_sel, descendant_sel)

        self.assertTrue(selector.matches(child))

    def test_not_matches_wrong_descendant(self):
        parent = Element("div", {}, None)
        child = Element("span", {}, parent)
        parent.children.append(child)

        ancestor_sel = Tagselector("div")
        descendant_sel = Tagselector("p")
        selector = DescendantSelector(ancestor_sel, descendant_sel)

        self.assertFalse(selector.matches(child))

    def test_not_matches_wrong_ancestor(self):
        root = Element("body", {}, None)
        parent = Element("div", {}, root)
        child = Element("p", {}, parent)

        root.children.append(parent)
        parent.children.append(child)

        ancestor_sel = Tagselector("html")
        descendant_sel = Tagselector("p")
        selector = DescendantSelector(ancestor_sel, descendant_sel)

        self.assertFalse(selector.matches(child))

    def test_matches_no_parent(self):
        child = Element("p", {}, None)

        ancestor_sel = Tagselector("div")
        descendant_sel = Tagselector("p")
        selector = DescendantSelector(ancestor_sel, descendant_sel)

        self.assertFalse(selector.matches(child))


class TestCSSParserParse(unittest.TestCase):
    """parse() メソッドのテスト"""

    def test_empty_string(self):
        parser = CSSParser("")
        rules = parser.parse()
        self.assertEqual(rules, [])

    def test_single_rule(self):
        parser = CSSParser("div{color: red;}")
        rules = parser.parse()
        self.assertEqual(len(rules), 1)
        selector, body = rules[0]
        self.assertIsInstance(selector, Tagselector)
        self.assertEqual(selector.tag, "div")
        self.assertEqual(body, {"color": "red"})

    def test_multiple_rules(self):
        parser = CSSParser("div{color: red;} p{color: blue;}")
        rules = parser.parse()
        self.assertEqual(len(rules), 2)

    def test_rule_with_multiple_properties(self):
        parser = CSSParser(
            "div{color: red; background: blue; fontsize: 12;}")
        rules = parser.parse()
        selector, body = rules[0]
        self.assertIn("color", body)
        self.assertIn("background", body)
        self.assertIn("fontsize", body)

    def test_descendant_selector_rule(self):
        parser = CSSParser("div p{color: red;}")
        rules = parser.parse()
        selector, body = rules[0]
        self.assertIsInstance(selector, DescendantSelector)
        self.assertIn("color", body)

    def test_rule_with_extra_whitespace(self):
        parser = CSSParser("div{color:red;}")
        rules = parser.parse()
        self.assertEqual(len(rules), 1)
        selector, body = rules[0]
        self.assertEqual(selector.tag, "div")
        self.assertEqual(body, {"color": "red"})

    def test_invalid_rule_recovered(self):
        # invalid rule を skip して次のルールを読む
        parser = CSSParser("div{invalid rule} p{color: blue;}")
        rules = parser.parse()
        # 最初のルールは不正でスキップされるが、2番目のルールは読まれるべき
        self.assertGreaterEqual(len(rules), 1)

    def test_multiple_rules_complex(self):
        css = "html{color: black;} body{background: white;} div p{fontsize: 12;}"
        parser = CSSParser(css)
        rules = parser.parse()
        self.assertEqual(len(rules), 3)

    def test_case_insensitive_parsing(self):
        parser = CSSParser("DIV{COLOR: RED;}")
        rules = parser.parse()
        selector, body = rules[0]
        self.assertEqual(selector.tag, "div")
        self.assertEqual(body, {"color": "RED"})

    def test_rule_with_hex_color(self):
        parser = CSSParser("div{color: #ff0000;}")
        rules = parser.parse()
        selector, body = rules[0]
        self.assertIn("color", body)
        self.assertTrue(body["color"].startswith("#"))

    def test_rule_with_percentage_value(self):
        parser = CSSParser("div{width: 50%;}")
        rules = parser.parse()
        selector, body = rules[0]
        self.assertIn("width", body)
        self.assertEqual(body["width"], "50%")


class TestCSSParserIntegration(unittest.TestCase):
    """統合テスト"""

    def test_realistic_css_simple(self):
        css = "body{fontsize: 14; color: black;}"
        parser = CSSParser(css)
        rules = parser.parse()
        self.assertEqual(len(rules), 1)
        selector, body = rules[0]
        self.assertEqual(selector.tag, "body")
        self.assertEqual(body["fontsize"], "14")
        self.assertEqual(body["color"], "black")

    def test_realistic_css_complex(self):
        css = "html{background: white;} body{margin: 0;} div{color: red;} div p{fontsize: 12; color: blue;}"
        parser = CSSParser(css)
        rules = parser.parse()
        self.assertEqual(len(rules), 4)

    def test_css_with_inline_style(self):
        # inline style (body メソッド) をテスト
        css = "color: red; background: blue; fontsize: 12;"
        parser = CSSParser(css)
        body = parser.body()
        self.assertEqual(
            body, {"color": "red", "background": "blue", "fontsize": "12"})

    def test_parser_position_tracking(self):
        parser = CSSParser("div{color: red;}")
        rules = parser.parse()
        # パースが終わった後、位置がスタイルの最後にある
        self.assertEqual(parser.i, len(parser.s))


if __name__ == "__main__":
    unittest.main()
