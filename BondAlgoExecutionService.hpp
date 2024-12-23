#ifndef BOND_ALGO_EXECUTION_SERVICE_HPP
#define BOND_ALGO_EXECUTION_SERVICE_HPP

#include <string>
#include <iostream>
#include "soa.hpp"
#include "marketdataservice.hpp"
#include "executionservice.hpp"

using namespace std;

// Template class for Algorithmic Execution
template <typename ProductType>
class AlgoExecution {
private:
    ExecutionOrder<ProductType>* execution_order; // Pointer to an execution order object
    Market execution_market;                       // The market in which the execution occurs
    static int id_counter;                         // Static counter to generate unique IDs

public:
    // Constructor to initialize AlgoExecution based on market data
    AlgoExecution(const OrderBook<ProductType>& order_book)
        : execution_market(CME) // Assuming CME is a predefined Market enum
    {
        id_counter++;

        // Determine the pricing side (alternating between BID and OFFER)
        PricingSide order_side = static_cast<PricingSide>(id_counter % 2);

        // Generate unique ID for the execution order
        string generated_order_id = to_string(id_counter);

        // Extract product from the order book
        ProductType bond_product = order_book.GetProduct();

        // Extract price and quantity based on order side
        double execution_price = (order_side == BID) ?
            order_book.GetBidStack()[0].GetPrice() :
            order_book.GetOfferStack()[0].GetPrice();

        long order_quantity = (order_side == BID) ?
            order_book.GetOfferStack()[0].GetQuantity() :
            order_book.GetBidStack()[0].GetQuantity();

        // Calculate hidden quantity
        double hidden_quantity_ratio = 0.9;
        long hidden_quantity = static_cast<long>(order_quantity * hidden_quantity_ratio);

        // Create the ExecutionOrder object
        execution_order = new ExecutionOrder<ProductType>(
            bond_product,
            order_side,
            generated_order_id,
            MARKET,
            execution_price,
            order_quantity,
            hidden_quantity,
            generated_order_id,
            false
        );
    }

    // Getter for the ExecutionOrder
    ExecutionOrder<ProductType> GetExecutionOrder() const {
        return *execution_order;
    }

    // Getter for the execution market
    Market GetExecutionMarket() const {
        return execution_market;
    }

    // Destructor to free allocated memory
    ~AlgoExecution() {
        delete execution_order;
    }
};

// Initialize the static member
template <typename ProductType>
int AlgoExecution<ProductType>::id_counter = 0;


// Bond Algorithmic Execution Service class
template <typename ProductType>
class BondAlgoExecutionService : public Service<string, AlgoExecution<ProductType>> {
public:
    // Execute method to process market data and generate AlgoExecution
    void Execute(const OrderBook<ProductType>& order_book) {
        // Extract top-of-book prices for bids and offers
        double highest_bid = order_book.GetBidStack()[0].GetPrice();
        double lowest_offer = order_book.GetOfferStack()[0].GetPrice();

        // Calculate bid-offer spread
        double bid_offer_spread = lowest_offer - highest_bid;

        // Spread tolerance, calculated as 1/127
        double spread_tolerance = 1.0 / 127.0;

        // Check if the spread is within tolerance before executing
        if (bid_offer_spread <= spread_tolerance)
        {
            // Create an instance of AlgoExecution
            AlgoExecution<ProductType> algo_execution(order_book);

            // Notify the subscribers with the new AlgoExecution instance
            this->Notify(algo_execution);
        }
    }
};

#endif
