package dev.aiengg.potholereporter.drive

/** Strict bounded JSON grammar before Android's permissive/recursive JSONObject parser. */
internal object NativeInferenceJsonSyntax {
    const val MAX_DEPTH = 32

    fun requireObject(text: String) {
        if (text.length > 64 * 1024) throw NativeSseSafetyException()
        Parser(text).parse()
    }

    private class Parser(private val text: String) {
        private var index = 0
        private fun invalid(): Nothing = throw NativeSseSafetyException()
        private fun current(): Char? = text.getOrNull(index)
        private fun whitespace() { while (current() in listOf(' ', '\t', '\r', '\n')) index++ }
        private fun take(expected: Char) { if (current() != expected) invalid(); index++ }
        fun parse() {
            whitespace()
            if (current() != '{') invalid()
            value(0)
            whitespace()
            if (index != text.length) invalid()
        }
        private fun value(depth: Int) {
            whitespace()
            if (depth >= MAX_DEPTH) invalid()
            when (current()) {
                '{' -> {
                    index++; whitespace()
                    if (current() == '}') { index++; return }
                    while (true) {
                        whitespace(); string(); whitespace(); take(':'); value(depth + 1); whitespace()
                        if (current() == '}') { index++; return }
                        take(',')
                    }
                }
                '[' -> {
                    index++; whitespace()
                    if (current() == ']') { index++; return }
                    while (true) {
                        value(depth + 1); whitespace()
                        if (current() == ']') { index++; return }
                        take(',')
                    }
                }
                '"' -> string()
                't' -> literal("true")
                'f' -> literal("false")
                'n' -> literal("null")
                '-', in '0'..'9' -> number()
                else -> invalid()
            }
        }
        private fun literal(value: String) {
            if (!text.regionMatches(index, value, 0, value.length)) invalid()
            index += value.length
        }
        private fun string() {
            take('"')
            while (true) {
                val c = current() ?: invalid()
                index++
                if (c == '"') return
                if (c.code < 32) invalid()
                if (c != '\\') continue
                val escaped = current() ?: invalid(); index++
                if (escaped == 'u') {
                    repeat(4) {
                        val hex = current() ?: invalid()
                        if (hex !in '0'..'9' && hex !in 'a'..'f' && hex !in 'A'..'F') invalid()
                        index++
                    }
                } else if (escaped !in listOf('"', '\\', '/', 'b', 'f', 'n', 'r', 't')) invalid()
            }
        }
        private fun number() {
            if (current() == '-') index++
            if (current() == '0') index++ else {
                if (current() !in '1'..'9') invalid()
                while (current() in '0'..'9') index++
            }
            if (current() == '.') { index++; digits() }
            if (current() == 'e' || current() == 'E') {
                index++; if (current() == '+' || current() == '-') index++
                digits()
            }
        }
        private fun digits() {
            if (current() !in '0'..'9') invalid()
            while (current() in '0'..'9') index++
        }
    }
}
