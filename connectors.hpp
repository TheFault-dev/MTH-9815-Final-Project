#ifndef CONNECTORS_HPP
#define CONNECTORS_HPP

#include <chrono>
#include <fstream>
#include <iostream>
#include <string>
#include <tuple>
#include <unordered_map>

#include "executionservice.hpp"
#include "inquiryservice.hpp"
#include "marketdataservice.hpp"
#include "parser.hpp"
#include "positionservice.hpp"
#include "pricingservice.hpp"
#include "productmap.hpp"
#include "riskservice.hpp"
#include "soa.hpp"
#include "streamingservice.hpp"
#include "tradebookingservice.hpp"

using namespace std;
using namespace std::chrono;

template<typename V>
class PricingConnector : public Connector<Price<V>> {
private:
    string file_name;
    PricingService<V>* pricing_service;

public:
    explicit PricingConnector(string file_name_, PricingService<V>* pricing_service_)
        : file_name(file_name_), pricing_service(pricing_service_) {
    }

    virtual void Publish(const Price<V>& data) {}

    void Subscribe() {
        string line;
        ifstream file(file_name);
        int curr_line = 0;

        if (file.is_open()) {
            cerr << "[INFO] Starting price data loading process..." << endl;
            vector<string> line_elements;

            while (getline(file, line)) {
                curr_line++;
                if (curr_line % 100000 == 0)
                    cerr << "[INFO] Processed " << curr_line << " prices..." << endl;

                line_elements = Parser::clean_csv(line);
                unordered_map<string, Bond> product_map = ProductMap::GetProductMap();

                string productID = line_elements[0];
                Bond product = product_map[productID];
                double bid = Parser::convert_price(line_elements[1]);
                double ask = Parser::convert_price(line_elements[2]);
                double mid = (bid + ask) / 2;
                double spread = ask - bid;

                Price<V> price(product, mid, spread);
                pricing_service->OnMessage(price);
            }
        }
        else {
            cerr << "[ERROR] Failed to open the file: " << file_name << endl;
        }
    }
};

template<typename V>
class PositionConnector : public Connector<Position<V>> {
private:
    string file_name;

public:
    explicit PositionConnector(string file_name_) : file_name(file_name_) {
        ofstream out(file_name, ios::trunc);
    }
    
    virtual void Publish(const Position<V>& data) {
        ofstream out(file_name, ios::app);
        string book_name[3] = { "TRSY1", "TRSY2", "TRSY3" };
        long aggregate = 0;

        for (string& book : book_name) {
            aggregate += data.GetPosition(book);
        }

        milliseconds ms = duration_cast<milliseconds>(system_clock::now().time_since_epoch());
        out << ms.count() << "," << data.GetProduct().GetTicker() << ","
            << data.GetPosition(book_name[0]) << ","
            << data.GetPosition(book_name[1]) << ","
            << data.GetPosition(book_name[2]) << ","
            << aggregate << endl;
    }
};

template<typename V>
class RiskConnector : public Connector<PV01<V>> {
private:
    string file_name;

public:
    explicit RiskConnector(string file_name_) : file_name(file_name_) {
        ofstream out(file_name, ios::trunc);
    }

    virtual void Publish(const PV01<V>& data) {
        ofstream out(file_name, ios::app);
        milliseconds ms = duration_cast<milliseconds>(system_clock::now().time_since_epoch());
        out << ms.count() << "," << data.GetProduct().GetTicker() << ","
            << data.GetTotalPV01() << endl;
    }
};

template<typename V>
class StreamingConnector : public Connector<PriceStream<V>> {
private:
    string file_name;

public:
    explicit StreamingConnector(const string& file_name_) : file_name(file_name_) {
        ofstream out(file_name, ios::trunc);
    }

    virtual void Publish(const PriceStream<V>& data) {
        ofstream out(file_name, ios::app);
        milliseconds ms = duration_cast<milliseconds>(system_clock::now().time_since_epoch());
        out << ms.count() << "," << data.GetProduct().GetTicker() << ","
            << data.GetBidOrder().GetPrice() << ","
            << data.GetOfferOrder().GetPrice() << endl;
    }
};

template<typename V>
class TradeBookingConnector : public Connector<Trade<V>> {
private:
    string file_name;
    TradeBookingService<V>* tradebookingservice;

public:
    explicit TradeBookingConnector(string file_name_, TradeBookingService<V>* tradebookingservice_)
        : file_name(file_name_), tradebookingservice(tradebookingservice_) {
    }

    virtual void Publish(const Trade<V>& data) {}

    void TraverseTrades() {
        string line;
        ifstream file(file_name);

        if (file.is_open()) {
            vector<string> line_elements;
            while (getline(file, line)) {
                cerr << "[INFO] Parsing trade data: " << line << endl;
                line_elements = Parser::clean_csv(line);
                unordered_map<string, Bond> product_map = ProductMap::GetProductMap();

                string productID = line_elements[0];
                Bond product = product_map[productID];
                string tradeID = line_elements[1];
                double price = atof(line_elements[4].c_str());
                string book = line_elements[2];
                long quantity = atol(line_elements[3].c_str());
                Side side = (line_elements[5][0] == 'B') ? BUY : SELL;

                Trade<Bond> trade(product, tradeID, price, book, quantity, side);
                tradebookingservice->OnMessage(trade);
            }
        }
        else {
            cerr << "[ERROR] Failed to open the trade data file: " << file_name << endl;
        }
    }
};

template<typename V>
class GUIConnector : public Connector<Price<V>> {
private:
    string file_name;

public:
    explicit GUIConnector(string file_name_) : file_name(file_name_) {
        ofstream out(file_name, ios::trunc);
    }

    virtual void Publish(const Price<V>& data) {
        ofstream out(file_name, ios::app);
        milliseconds ms = duration_cast<milliseconds>(system_clock::now().time_since_epoch());
        out << ms.count() << "," << data.GetProduct().GetTicker()
            << "," << data.GetMid() << "," << data.GetBidOfferSpread() << endl;
    }
};

template<typename V>
class MarketDataConnector : public Connector<OrderBook<V>> {
private:
    string file_name;
    MarketDataService<V>* marketdataservice;

public:
    explicit MarketDataConnector(const string& file_name_,
        MarketDataService<V>* marketdataservice_)
        : file_name(file_name_), marketdataservice(marketdataservice_) {
    }

    virtual void Publish(const OrderBook<V>& data) {}

    void Subscribe() {
        string line;
        ifstream file(file_name);

        if (file.is_open()) {
            cerr << "[INFO] Loading order book data..." << endl;
            vector<string> parsed_elements;
            int count = 0;

            while (getline(file, line)) {
                if (++count % 100000 == 0) {
                    cerr << "[INFO] Processed " << count << " order books." << endl;
                }

                auto [ticker, prices] = Parser::extract_order_book(line);
                vector<Order> bid_stack;
                vector<Order> offer_stack;

                for (int i = 0; i < 5; ++i) {
                    bid_stack.emplace_back(prices[i * 2], 1000000 * (i + 1), BID);
                    offer_stack.emplace_back(prices[i * 2 + 1], 1000000 * (i + 1), OFFER);
                }

                unordered_map<string, Bond> product_map = ProductMap::GetProductMap();
                Bond product = product_map[ticker];

                OrderBook<Bond> order_book(product, bid_stack, offer_stack);
                marketdataservice->ProcessOrderBook(order_book);
            }
        }
        else {
            cerr << "[ERROR] Failed to open the file: " << file_name << endl;
        }
    }
};

template<typename V>
class ExecutionConnector : public Connector<ExecutionOrder<V>> {
private:
    string file_name;

public:
    explicit ExecutionConnector(string file_name_) : file_name(file_name_) {
        ofstream out(file_name, ios::trunc);
    }

    virtual void Publish(const ExecutionOrder<V>& data) {
        ofstream out(file_name, ios::app);
        milliseconds ms = duration_cast<milliseconds>(system_clock::now().time_since_epoch());
        string side = (data.GetPricingSide() == BID) ? "BUY" : "SELL";

        out << ms.count() << "," << data.GetProduct().GetTicker()
            << ",TID_" << data.GetOrderId() << ",MarketOrder"
            << "," << side << "," << data.GetPrice()
            << "," << data.GetVisibleQuantity() << "," << data.GetHiddenQuantity()
            << endl;
    }
};

template<typename V>
class InquiryConnector : public Connector<Inquiry<V>> {
private:
    string file_name;
    InquiryService<V>* inquiry_service;

public:
    explicit InquiryConnector(string file_name_, InquiryService<V>* inquiry_service_)
        : file_name(file_name_), inquiry_service(inquiry_service_) {
    }

    virtual void Publish(const Inquiry<V>& data) {
        InquiryState inquiry_state = data.GetState();
        if (inquiry_state == RECEIVED) {
            Inquiry<V> updated_inquiry = data;
            updated_inquiry.SetState(QUOTED);
            inquiry_service->OnMessage(updated_inquiry);

            updated_inquiry.SetState(DONE);
            inquiry_service->OnMessage(updated_inquiry);
        }
    }

    void Subscribe() {
        string line;
        ifstream file(file_name);
        if (file.is_open()) {
            cerr << "[INFO] Processing inquiries from file: " << file_name << endl;
            vector<string> line_elements;

            while (getline(file, line)) {
                cerr << "[INFO] Parsing inquiry: " << line << endl;
                line_elements = Parser::clean_csv(line);

                string quote_id = line_elements[0];
                string ticker = line_elements[1];
                Side side = (line_elements[2][0] == 'B') ? BUY : SELL;

                unordered_map<string, Bond> product_map = ProductMap::GetProductMap();
                Bond product = product_map[ticker];

                Inquiry<Bond> inquiry(quote_id, product, side, 1000000, -1, RECEIVED);
                inquiry_service->OnMessage(inquiry);
            }
        }
        else {
            cerr << "[ERROR] Unable to open the file: " << file_name << endl;
        }
    }
};

template<typename V>
class AllInquiriesConnector : public Connector<Inquiry<V>> {
private:
    string file_name;

public:
    explicit AllInquiriesConnector(string file_name_) : file_name(file_name_) {
        ofstream out(file_name, ios::trunc);
    }

    virtual void Publish(const Inquiry<V>& data) {
        ofstream out(file_name, ios::app);
        milliseconds ms = duration_cast<milliseconds>(system_clock::now().time_since_epoch());

        string state = (data.GetState() == RECEIVED) ? "RECEIVED" :
            (data.GetState() == QUOTED) ? "QUOTED" : "DONE";
        string side = (data.GetSide() == BUY) ? "BUY" : "SELL";

        out << ms.count() << "," << "TID_" << data.GetInquiryId()
            << "," << data.GetProduct().GetTicker() << "," << side
            << "," << data.GetPrice() << "," << state << endl;
    }
};

#endif
