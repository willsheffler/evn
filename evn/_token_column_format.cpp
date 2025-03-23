#include <algorithm>
#include <cctype>
#include <exception>
#include <iostream>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>

namespace py = pybind11;
using namespace std;

enum class TokenType {
    Identifier,
    String,
    Numeric,
    Exact // Keywords, punctuation, comments, etc.
};

// Helper struct to store per–line data.
struct LineInfo {
    int lineno;             // Line number.
    string line;            // Original line.
    string indent;          // Leading whitespace.
    string content;         // Line without indent.
    vector<string> tokens;  // Tokenized content.
    vector<string> pattern; // Token pattern (wildcards)
};

string rstrip(const string &str) {
    string trimmed_str = str;
    auto it = find_if(trimmed_str.rbegin(), trimmed_str.rend(),
                      [](unsigned char ch) { return !isspace(ch); });
    trimmed_str.erase(it.base(), trimmed_str.end());
    return trimmed_str;
}

class PythonLineTokenizer {
  public:
    // Reformat the given code buffer (as a string) into a new string.
    // Each line is processed, and consecutive lines that share the same
    // token pattern (by wildcard) and the same indentation are grouped and
    // aligned. If add_fmt_tag is true, formatting tags are added.
    string reformat_buffer(const string &code, bool add_fmt_tag = false,
                           bool debug = false) {
        istringstream stream(code);
        string line;
        vector<string> lines;
        while (getline(stream, line)) lines.push_back(line);
        vector<string> output = reformat_lines(lines, add_fmt_tag, debug);
        ostringstream result;
        for (const auto &outline : output) result << outline << "\n";
        return result.str();
    }

    // Process a vector of lines.
    vector<string> reformat_lines(const vector<string> &lines,
                                  bool add_fmt_tag = false,
                                  bool debug = false) {
        vector<LineInfo> infos = line_info(lines);
        vector<string> output;
        vector<LineInfo> block;
        const size_t length_threshold = 10;
        for (const auto &info : infos) {
            if (debug) cout << "reformat " << info.lineno << info.line << endl;
            // Blank lines are output as-is.
            if (info.content.empty()) {
                flush_block(block, output);
                output.push_back(rstrip(info.line));
                continue;
            }
            if (block.empty()) {
                block.push_back(info);
            } else {
                // Group lines if indent and token pattern match, and if lengths
                // are similar.
                try {
                    if (info.indent != block.at(0).indent ||
                        abs(static_cast<int>(info.line.size()) -
                            static_cast<int>(block.at(0).line.size())) >
                            length_threshold ||
                        info.pattern != block.at(0).pattern) {
                        flush_block(block, output, add_fmt_tag, debug);
                    }
                } catch (const out_of_range &e) {
                    throw runtime_error("Error grouping lines: " +
                                        string(e.what()));
                }
                block.push_back(info);
            }
        }
        flush_block(block, output, add_fmt_tag, debug);
        return output;
    }

    // Tokenizes a single line of Python code.
    vector<string> tokenize(const string &line) {
        vector<string> tokens;
        size_t i = 0;
        while (i < line.size()) {
            // Skip whitespace.
            if (isspace(static_cast<unsigned char>(line.at(i)))) {
                ++i;
                continue;
            }
            // Handle comments: rest of the line is one token.
            if (line.at(i) == '#') {
                tokens.push_back(line.substr(i));
                break;
            }
            // Check for an f-string literal.
            if ((line.at(i) == 'f' || line.at(i) == 'F') &&
                (i + 1 < line.size()) &&
                (line.at(i + 1) == '\'' || line.at(i + 1) == '"')) {
                tokens.push_back(parse_string_literal(line, i, true));
                continue;
            }
            // Check for a normal string literal.
            if (line.at(i) == '\'' || line.at(i) == '"') {
                tokens.push_back(parse_string_literal(line, i, false));
                continue;
            }
            // Check for an identifier or keyword.
            if (isalpha(static_cast<unsigned char>(line.at(i))) ||
                line.at(i) == '_') {
                size_t start = i;
                while (i < line.size() &&
                       (isalnum(static_cast<unsigned char>(line.at(i))) ||
                        line.at(i) == '_')) {
                    ++i;
                }
                tokens.push_back(line.substr(start, i - start));
                continue;
            }
            // Handle numeric literals in a basic way.
            if (isdigit(static_cast<unsigned char>(line.at(i)))) {
                size_t start = i;
                while (i < line.size() &&
                       (isdigit(static_cast<unsigned char>(line.at(i))) ||
                        line.at(i) == '.' || line.at(i) == 'e' ||
                        line.at(i) == 'E' || line.at(i) == '+' ||
                        line.at(i) == '-')) {
                    ++i;
                }
                tokens.push_back(line.substr(start, i - start));
                continue;
            }
            // Check for multi-character punctuation/operators.
            bool multi_matched = false;
            static const vector<string> multi_tokens = {
                "...", "==", "!=", "<=", ">=", "//", "**", "->", "+=",
                "-=",  "*=", "/=", "%=", "&=", "|=", "^=", ">>", "<<"};
            for (const auto &tok : multi_tokens) {
                if (line.compare(i, tok.size(), tok) == 0) {
                    tokens.push_back(tok);
                    i += tok.size();
                    multi_matched = true;
                    break;
                }
            }
            if (multi_matched) continue;
            // Single-character punctuation.
            try {
                tokens.push_back(string(1, line.at(i)));
            } catch (const out_of_range &e) {
                throw runtime_error("Index error in tokenize at position " +
                                    to_string(i));
            }
            ++i;
        }
        return tokens;
    }

    // Returns a token pattern for grouping.
    vector<string> get_token_pattern(const vector<string> &tokens) {
        vector<string> pattern;
        for (const auto &tok : tokens) {
            if (is_string_literal(tok))
                pattern.push_back("STR");
            else if (is_identifier(tok) && !is_keyword(tok))
                pattern.push_back("ID");
            else if (!tok.empty() &&
                     isdigit(static_cast<unsigned char>(tok.at(0))))
                pattern.push_back("NUM");
            else
                pattern.push_back(tok);
        }
        return pattern;
    }

    // Formats tokens by computing a delimiter for each token (except the
    // first). (This implementation is largely unchanged; error checking can be
    // added as needed.)
    vector<string> format_tokens(const vector<string> &tokens) {
        vector<string> formatted;
        if (tokens.empty()) return formatted;
        formatted.resize(tokens.size());
        formatted.at(0) = tokens.at(0); // first token: no preceding delimiter

        bool in_param_context = false;
        bool is_def = (tokens.at(0) == "def");
        bool is_lambda = (tokens.at(0) == "lambda");
        if (is_def) {
            in_param_context = false;
        } else if (is_lambda) {
            in_param_context = true;
        }

        int depth = 0;
        for (size_t i = 1; i < tokens.size(); i++) {
            string prev = tokens.at(i - 1);
            if (prev == "(") {
                depth++;
                if (is_def) in_param_context = true;
            } else if (prev == ")") {
                depth--;
                if (is_def && depth == 0) in_param_context = false;
            }
            if (is_lambda && tokens.at(i) == ":") { in_param_context = false; }
            string delim = delimiter(i - 1, i, tokens, in_param_context, depth);
            formatted.at(i) = delim + tokens.at(i);
        }
        return formatted;
    }

    // Joins tokens into a single string.
    // If skip_formatting is true, assumes tokens are already formatted.
    string join_tokens(const vector<string> &tokens,
                       const vector<int> &widths = vector<int>(),
                       const vector<char> &justifications = vector<char>(),
                       bool skip_formatting = false) {
        vector<string> formatted_tokens(tokens);
        if (!skip_formatting) formatted_tokens = format_tokens(tokens);
        if (!widths.empty() && widths.size() == formatted_tokens.size() &&
            !justifications.empty() &&
            justifications.size() == formatted_tokens.size()) {
            for (size_t i = 0; i < formatted_tokens.size(); i++) {
                if (widths.at(i) > 0) {
                    int token_len =
                        static_cast<int>(formatted_tokens.at(i).size());
                    int padding = static_cast<int>(widths.at(i)) - token_len;
                    if (padding > 0) {
                        char just = justifications.at(i);
                        if (just == 'L' || just == 'l') {
                            formatted_tokens.at(i).append(padding, ' ');
                        } else if (just == 'R' || just == 'r') {
                            formatted_tokens.at(i).insert(0, padding, ' ');
                        } else if (just == 'C' || just == 'c') {
                            int pad_left = padding / 2;
                            int pad_right = padding - pad_left;
                            formatted_tokens.at(i).insert(0, pad_left, ' ');
                            formatted_tokens.at(i).append(pad_right, ' ');
                        }
                    }
                }
            }
        }
        string result;
        for (const auto &tok : formatted_tokens) result += tok;
        return rstrip(result);
    }

    // Returns a vector of LineInfo for each line.
    vector<LineInfo> line_info(const vector<string> &lines) {
        vector<LineInfo> infos;
        for (int i = 0; i < lines.size(); i++) {
            LineInfo info;
            info.lineno = i;
            info.line = lines[i];
            size_t pos = info.line.find_first_not_of(" \t");
            info.indent =
                (pos == string::npos) ? info.line : info.line.substr(0, pos);
            info.content = (pos == string::npos) ? "" : info.line.substr(pos);
            if (!info.content.empty()) {
                info.tokens = tokenize(info.content);
                info.pattern = get_token_pattern(info.tokens);
            }
            infos.push_back(info);
        }
        return infos;
    }

    // Compares two token vectors using wildcard rules.
    bool tokens_match(const vector<string> &tokens1,
                      const vector<string> &tokens2) {
        if (tokens1.size() != tokens2.size()) return false;
        for (size_t i = 0; i < tokens1.size(); i++) {
            TokenType type1 = get_token_type(tokens1.at(i));
            TokenType type2 = get_token_type(tokens2.at(i));
            if (type1 != type2) return false;
            if (type1 == TokenType::Exact && tokens1.at(i) != tokens2.at(i))
                return false;
        }
        return true;
    }

  private:
    // Flushes a block of LineInfo objects into output.
    void flush_block(vector<LineInfo> &block, vector<string> &output,
                     bool add_fmt_tag = false, bool debug = false) {
        if (block.empty()) return;
        if (block.size() == 1) {
            LineInfo const &info = block.at(0);
            if (is_oneline_statement(info.line)) {
                output.push_back(info.indent + "#             fmt: off");
                output.push_back(rstrip(info.line));
                output.push_back(info.indent + "#             fmt: on");
            } else {
                output.push_back(rstrip(info.line));
            }
        } else {
            vector<vector<string>> token_lines;
            for (const auto &info : block) token_lines.push_back(info.tokens);
            vector<vector<string>> formatted_lines;
            for (auto &tokens : token_lines)
                formatted_lines.push_back(format_tokens(tokens));
            size_t nTokens = 0;
            for (auto &tokens : formatted_lines)
                nTokens = max(nTokens, tokens.size());
            vector<int> max_width(nTokens, 0);
            for (auto &tokens : formatted_lines) {
                for (size_t j = 0; j < tokens.size(); j++) {
                    max_width.at(j) = max(
                        max_width.at(j), static_cast<int>(tokens.at(j).size()));
                }
            }
            vector<char> justifications(nTokens, 'L');
            if (add_fmt_tag)
                output.push_back(block.at(0).indent + "#             fmt: off");
            for (auto &tokens : formatted_lines) {
                string joined =
                    join_tokens(tokens, max_width, justifications, true);
                output.push_back(block.at(0).indent + joined);
            }
            if (add_fmt_tag)
                output.push_back(block.at(0).indent + "#             fmt: on");
        }
        block.clear();
    }

    // Delimiter helper: returns the delimiter to insert before the current
    // token.
    string delimiter(size_t prev_index, size_t curr_index,
                     const vector<string> &tokens, bool in_param_context,
                     int depth) const {
        const string &prev = tokens.at(prev_index);
        const string &next = tokens.at(curr_index);
        if (in_param_context && (prev == "=" || next == "=")) return "";
        if (is_operator(prev) || is_operator(next)) {
            if (depth > 1 &&
                (prev == "+" || prev == "-" || next == "+" || next == "-"))
                return "";
            return " ";
        }
        if (is_opener(prev)) return "";
        if (is_closer(next)) return "";
        if (next == "," || next == ":" || next == ";") return "";
        if (next == "(" && is_identifier_or_literal(prev) && !is_keyword(prev))
            return "";
        return " ";
    }

    // Parses a string literal from the given line starting at index i.
    string parse_string_literal(const string &line, size_t &i,
                                bool is_f_string) {
        size_t start = i;
        if (is_f_string) ++i; // skip the 'f' or 'F'
        if (i >= line.size())
            throw out_of_range("String literal start index out of range");
        char quote = line.at(i);
        bool triple = false;
        if (i + 2 < line.size() && line.at(i) == line.at(i + 1) &&
            line.at(i) == line.at(i + 2)) {
            triple = true;
            i += 3;
        } else {
            ++i;
        }
        while (i < line.size()) {
            if (line.at(i) == '\\') {
                i += 2;
            } else if (triple) {
                if (i + 2 < line.size() && line.at(i) == quote &&
                    line.at(i + 1) == quote && line.at(i + 2) == quote) {
                    i += 3;
                    break;
                } else {
                    ++i;
                }
            } else {
                if (line.at(i) == quote) {
                    ++i;
                    break;
                } else {
                    ++i;
                }
            }
        }
        return line.substr(start, i - start);
    }

    // Helper functions for token type checking.
    bool is_string_literal(const string &token) const {
        if (token.empty()) return false;
        if (token.at(0) == '\'' || token.at(0) == '"') return true;
        if (token.size() >= 2 && (token.at(0) == 'f' || token.at(0) == 'F') &&
            (token.at(1) == '\'' || token.at(1) == '"'))
            return true;
        return false;
    }

    bool is_identifier(const string &token) const {
        if (token.empty()) return false;
        if (!isalpha(static_cast<unsigned char>(token.at(0))) &&
            token.at(0) != '_')
            return false;
        for (size_t i = 1; i < token.size(); i++) {
            if (!isalnum(static_cast<unsigned char>(token.at(i))) &&
                token.at(i) != '_')
                return false;
        }
        return true;
    }

    bool is_opener(const string &token) const {
        return token == "(" || token == "[" || token == "{";
    }

    bool is_closer(const string &token) const {
        return token == ")" || token == "]" || token == "}";
    }

    bool is_operator(const string &token) const {
        static const unordered_set<string> operators = {
            "+",  "-",  "*",  "/",  "%", "**", "//", "==", "!=",
            "<",  ">",  "<=", ">=", "=", "->", "+=", "-=", "*=",
            "/=", "%=", "&",  "|",  "^", ">>", "<<", "~"};
        return operators.find(token) != operators.end();
    }

    bool is_keyword(const string &token) const {
        static const unordered_set<string> python_keywords = {
            "False",  "None",     "True",  "and",    "as",       "assert",
            "async",  "await",    "break", "class",  "continue", "def",
            "del",    "elif",     "else",  "except", "finally",  "for",
            "from",   "global",   "if",    "import", "in",       "is",
            "lambda", "nonlocal", "not",   "or",     "pass",     "raise",
            "return", "try",      "while", "with",   "yield"};
        return python_keywords.find(token) != python_keywords.end();
    }

    bool is_identifier_or_literal(const string &token) const {
        TokenType t = get_token_type(token);
        return (t == TokenType::Identifier || t == TokenType::String ||
                t == TokenType::Numeric);
    }

    TokenType get_token_type(const string &token) const {
        if (is_string_literal(token)) return TokenType::String;
        if (is_identifier(token)) {
            if (is_keyword(token)) return TokenType::Exact;
            return TokenType::Identifier;
        }
        if (!token.empty() && isdigit(static_cast<unsigned char>(token.at(0))))
            return TokenType::Numeric;
        return TokenType::Exact;
    }

    bool is_oneline_statement(string const &line) {
        if (line.empty()) { return false; }
        string trimmed = line;
        size_t firstNonSpace = trimmed.find_first_not_of(" \t");
        if (firstNonSpace == string::npos) return false; // Empty line
        trimmed = trimmed.substr(firstNonSpace);
        if (trimmed[0] == '#') { return false; }
        static const vector<string> keywords = {
            "if ", "elif ", "else:", "for ", "def ", "class "};

        bool foundKeyword = false;
        string keywordFound;
        for (const auto &keyword : keywords) {
            if (trimmed.compare(0, keyword.length(), keyword) == 0) {
                foundKeyword = true;
                keywordFound = keyword;
                break;
            }
        }
        if (!foundKeyword) { return false; }

        // Now we need to find the colon that ends the statement header
        size_t colonPos = 0;
        bool inString = false;
        char stringDelimiter = 0;
        bool escaped = false;
        int parenLevel = 0;

        // For else:, we already know the colon position
        if (keywordFound == "else:") {
            colonPos = firstNonSpace + 4; // "else" length
        } else {
            // For other keywords, we need to find the colon
            for (size_t i = 0; i < trimmed.length(); i++) {
                char c = trimmed[i];

                // Handle string delimiters
                if ((c == '"' || c == '\'') && !escaped) {
                    if (!inString) {
                        inString = true;
                        stringDelimiter = c;
                    } else if (c == stringDelimiter) {
                        inString = false;
                    }
                }

                // Handle escaping
                if (c == '\\' && !escaped) {
                    escaped = true;
                    continue;
                } else {
                    escaped = false;
                }

                // Track parentheses level (ignore if in string)
                if (!inString) {
                    if (c == '(' || c == '[' || c == '{') {
                        parenLevel++;
                    } else if (c == ')' || c == ']' || c == '}') {
                        parenLevel--;
                    } else if (c == ':' && parenLevel == 0) {
                        colonPos = firstNonSpace + i;
                        break;
                    }
                }
            }
        }

        // If we couldn't find a proper colon, it's not a valid statement
        if (colonPos == 0 || colonPos >= line.length() - 1) { return false; }

        // Now check if there's an action after the colon
        string afterColon = line.substr(colonPos + 1);
        size_t actionStart = afterColon.find_first_not_of(" \t");

        // If there's nothing after the colon or just a comment, it's not an
        // inline action
        if (actionStart == string::npos || afterColon[actionStart] == '#') {
            return false;
        }

        return true;
    }
};

PYBIND11_MODULE(_token_column_format, m) {
    m.doc() = "A module that wraps PythonLineTokenizer using pybind11";
    py::class_<PythonLineTokenizer>(m, "PythonLineTokenizer")
        .def(py::init<>())
        .def("tokenize", &PythonLineTokenizer::tokenize,
             "Tokenize a single line of Python code")
        .def("format_tokens", &PythonLineTokenizer::format_tokens,
             "Format tokens by prepending delimiters based on Black-like "
             "spacing heuristics")
        .def(
            "join_tokens",
            static_cast<string (PythonLineTokenizer::*)(
                const vector<string> &, const vector<int> &,
                const vector<char> &, bool)>(&PythonLineTokenizer::join_tokens),
            py::arg("tokens"), py::arg("widths") = vector<int>(),
            py::arg("justifications") = vector<char>(),
            py::arg("skip_formatting") = false,
            "Join tokens into a valid Python code line using Black-like "
            "heuristics. If skip_formatting is true, assume tokens are already "
            "formatted.")
        .def("tokens_match", &PythonLineTokenizer::tokens_match,
             "Compare two token vectors using wildcards for identifiers, "
             "strings, and numerics")
        .def("reformat_buffer", &PythonLineTokenizer::reformat_buffer,
             py::arg("code"), py::arg("add_fmt_tag") = false,
             py::arg("debug") = false,
             "Reformat a code buffer, grouping lines with matching token "
             "patterns and indentation into blocks and aligning them into evn "
             "columns.")
        .def("reformat_lines", &PythonLineTokenizer::reformat_lines,
             py::arg("lines"), py::arg("add_fmt_tag") = false,
             py::arg("debug") = false,
             "Reformat a code buffer (given as a vector of lines) by grouping "
             "lines with matching token patterns and indentation into blocks "
             "and aligning them into evn columns.");
}
