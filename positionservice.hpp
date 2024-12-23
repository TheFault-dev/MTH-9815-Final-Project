/**
 * positionservice.hpp
 * Defines the data types and Service for positions.
 *
 * @author Breman Thuraisingham
 */
#ifndef POSITION_SERVICE_HPP
#define POSITION_SERVICE_HPP

#include <string>
#include <map>
#include <unordered_map>
#include <tuple>

#include "soa.hpp"
#include "tradebookingservice.hpp"
#include "productmap.hpp"

using namespace std;

template<typename T>
class Position {
private:
    T product;
    map<string, long> positions;

public:
    Position(const T& product) : product(product) {
        array<string, 3> books{"TRSY1", "TRSY2", "TRSY3"};
        for (const auto& book : books) {
            positions.emplace(book, 0);
        }
    }

    const T& GetProduct() const {
        return product;
    }

    long GetPosition(const string& book) const {
        auto it = positions.find(book);
        if (it == positions.end()) {
            cerr << "GetPosition() error: Book not found - " << book << endl;
            return 0;
        }
        return it->second;
    }

    long GetAggregatePosition() const {
        long result = 0;
        for (const auto& [book, quantity] : positions) result += quantity;
        return result;
    }

    // Friend declaration to allow PositionService to access positions
    template<typename U>
    friend class PositionService;
};

template<typename T>
class PositionService : public Service<string, Position<T>> {
private:
    unordered_map<string, Position<T>> tickerToPositionMap;

    // Private helper to update position directly
    void UpdatePositionForBook(Position<T>& position, const string& book, long quantity, Side side) {
        auto& book_positions = position.positions;
        auto it = book_positions.find(book);
        if (it != book_positions.end()) {
            if (side == BUY) {
                it->second += quantity;
            } else if (side == SELL) {
                it->second -= quantity;
            }
        }
    }

public:
    PositionService() {
        unordered_map<string, Bond> bondMap = ProductMap::GetProductMap();
        vector<string> tickers = ProductMap::GetTickers();

        for (const auto& ticker : tickers) {
            auto bondIt = bondMap.find(ticker);
            if (bondIt != bondMap.end()) {
                Position<Bond> position(bondIt->second);
                tickerToPositionMap.emplace(ticker, position);
            }
        }
    }

    virtual void AddTrade(const Trade<T>& trade) {
        string ticker = trade.GetProduct().GetTicker();
        auto it = tickerToPositionMap.find(ticker);
        
        if (it != tickerToPositionMap.end()) {
            UpdatePositionForBook(it->second, trade.GetBook(), trade.GetQuantity(), trade.GetSide());
            Service<string, Position<T>>::Notify(it->second);
        } else {
            cout << "AddTrade() error: Ticker " << ticker << " does not exist!" << endl;
        }
    }

    virtual Position<T>& GetData(const string& key) {
        return tickerToPositionMap.find(key)->second;
    }
};

#endif
