/**
 * positionservice.hpp
 * Defines the data types and Service for positions.
 *
 * @author Breman Thuraisingham
 */
#ifndef POSITION_SERVICE_HPP
#define POSITION_SERVICE_HPP

#include "soa.hpp"
#include "tradebookingservice.hpp"
#include "productmap.hpp"

#include <string>
#include <map>
#include <unordered_map>
#include <tuple>

using namespace std;
template<typename T>
class Position
{
private:
    T product;
    map<string, long> positions;

public:
    // Constructor
    Position(const T& _product) : product(_product) {
        array<string, 3> books{"TRSY1", "TRSY2", "TRSY3"};
        for (const auto& book : books) {
            positions.emplace(book, 0);
        }
    }

    // Get the associated product
    const T& GetProduct() const {
        return product;
    }

    // Get position for a specific book
    long GetPosition(const string& book) const {
        auto it = positions.find(book);
        if (it == positions.end()) {
            cerr << "GetPosition() error: Book not found - " << book << endl;
            return 0; // Or throw an exception if preferred
        }
        return it->second;
    }

    // Get aggregate position across all books
    long GetAggregatePosition() const {
        long result = 0;
        for (const auto& [book, quantity] : positions) result += quantity;
        return result;
    }
    
    void UpdatePosition(string& book, long quantity, Side side)
    {
        if(side == BUY)
        {
            positions.find(book)->second += quantity;
        }
        else if(side == SELL)
        {
            positions.find(book)->second -= quantity;
        }
    }

};

// Template definition of PositionService
template<typename T>
class PositionService : public Service<string, Position<T>> {
private:
    // Map from tickers to their current positions
    unordered_map<string, Position<T>> tickerToPositionMap;

public:
    // Constructor initializes the service with default positions for all tickers
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

    // Add a trade to the service
    virtual void AddTrade(const Trade<T>& trade) {
        string ticker = trade.GetProduct().GetTicker();
        string book = trade.GetBook();
        long quantity = trade.GetQuantity();
        Side side = trade.GetSide();

        auto it = tickerToPositionMap.find(ticker);
        if (it != tickerToPositionMap.end()) {
            Position<Bond>& position = it->second;
            position.UpdatePosition(book, quantity, side);
        } else {
            cout << "AddTrade() error: Ticker " << ticker << " does not exist!" << endl;
        }

        Service<string, Position<T>>::Notify(tickerToPositionMap.find(ticker)->second);
    }

    // Retrieve position data for a given ticker
    virtual Position<T>& GetData(const string& key) {
        return tickerToPositionMap.find(key)->second;
    }
};






#endif
