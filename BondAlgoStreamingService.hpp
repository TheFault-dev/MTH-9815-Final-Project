#ifndef BOND_ALGO_STREAMING_SERVICE_HPP
#define BOND_ALGO_STREAMING_SERVICE_HPP

#include <tuple>
#include "soa.hpp"
#include "streamingservice.hpp"
#include "pricingservice.hpp"
#include "products.hpp"

// Template class for Bond Algorithmic Streaming Service
template<typename T>
class BondAlgoStreamingService : public Service<std::string, PriceStream<T>> {
public:
    // Method to publish price streams based on input price data
    void PublishPrice(Price<T>& price_data) {
        // Extract mid price and bid-offer spread from price data
        const double mid_price = price_data.GetMid();
        const double bid_offer_spread = price_data.GetBidOfferSpread();
        
        // Calculate prices for bid and ask orders
        const double half_spread = bid_offer_spread / 2;
        const double bid_price = mid_price - half_spread;
        const double ask_price = mid_price + half_spread;
        
        // Define standard quantities for orders
        constexpr long visible_quantity = 1000000;
        constexpr long hidden_quantity = visible_quantity;
        
        // Create bid order with calculated price and quantities
        PriceStreamOrder bid_order(
            bid_price,
            visible_quantity,
            hidden_quantity,
            BID
        );

        // Create ask order with calculated price and quantities
        PriceStreamOrder ask_order(
            ask_price,
            visible_quantity,
            hidden_quantity,
            OFFER
        );

        // Extract product from price data
        T bond_product = price_data.GetProduct();
        
        // Create price stream combining product and orders
        PriceStream<T> price_stream(
            bond_product,
            bid_order,
            ask_order
        );

        // Notify subscribers with the new price stream
        Service<std::string, PriceStream<T>>::Notify(price_stream);
    }
};

#endif
