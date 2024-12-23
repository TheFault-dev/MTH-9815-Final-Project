#ifndef PARSER_HPP
#define PARSER_HPP

#include <string>
#include <vector>
#include <sstream>
#include <tuple>

class Parser {
public:
    // Split CSV line into tokens
    static std::vector<std::string> tokenize_csv(const std::string& csv_line) {
        std::vector<std::string> tokens;
        std::istringstream stream(csv_line);
        std::string token;

        while (std::getline(stream, token, ',')) {
            tokens.push_back(token);
        }

        return tokens;
    }

    // Parse CSV with whitespace handling
    static std::vector<std::string> clean_csv(const std::string& raw_text) {
        std::vector<std::string> values;
        std::istringstream stream(raw_text);
        std::string segment;

        while (std::getline(stream, segment, ',')) {
            values.push_back(segment);
        }

        return values;
    }

    // Convert price format to decimal
    static double convert_price(const std::string& formatted_price) {
        const char* chars = formatted_price.c_str();
        int major = 0, minor = 0, frac = 0;
        int minor_start = 0;

        // Parse major part
        major = (chars[0] == '9') ? 99 : 100;
        minor_start = (chars[0] == '9') ? 3 : 4;

        // Parse minor and fractional parts
        minor = (chars[minor_start] - '0') * 10 +
                (chars[minor_start + 1] - '0');
        frac = (chars[minor_start + 2] - '0');

        return major + minor / 32.0 + frac / 256.0;
    }

    // Extract ticker and prices from order book data
    static std::tuple<std::string, std::vector<double>> extract_order_book(
            const std::string& order_book_data) {
        auto parts = tokenize_csv(order_book_data);
        std::vector<double> prices;
        prices.reserve(10);

        for (int i = 1; i <= 10; ++i) {
            prices.push_back(convert_price(parts[i]));
        }

        return {parts[0], prices};
    }
};

#endif
