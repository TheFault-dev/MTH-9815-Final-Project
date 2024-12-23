//  MTH 9815 Final Project
//
//  Created by Ruida Huang on 12/20/24.
//

#ifndef LISTENERS_HPP
#define LISTENERS_HPP

#include <tuple>
#include "historicaldataservice.hpp"
#include "executionservice.hpp"
#include "positionservice.hpp"
#include "riskservice.hpp"
#include "BondAlgoExecutionService.hpp"
#include "BondAlgoStreamingService.hpp"
#include "gui.hpp"

template<typename T>
class PositionServiceListener : public ServiceListener<Trade<T>> {
private:
    PositionService<T>* service_ptr_; ///< Pointer to PositionService

public:
    explicit PositionServiceListener(PositionService<T>* service_ptr)
        : service_ptr_(service_ptr) {}

    void ProcessAdd(Trade<T>& data) override {
        if (service_ptr_) {
            service_ptr_->AddTrade(data);
        }
    }

    void ProcessRemove(Trade<T>&) override {}
    void ProcessUpdate(Trade<T>&) override {}
};

template<typename T>
class RiskServiceListener : public ServiceListener<Position<T>> {
private:
    RiskService<T>* risk_service_; ///< Pointer to RiskService

public:
    explicit RiskServiceListener(RiskService<T>* risk_service)
        : risk_service_(risk_service) {}

    void ProcessAdd(Position<T>& data) override {
        if (risk_service_) {
            risk_service_->AddPosition(data);
        }
    }

    void ProcessRemove(Position<T>&) override {}
    void ProcessUpdate(Position<T>&) override {}
};

template<typename T>
class HistPositionListener : public ServiceListener<Position<T>> {
private:
    PositionHistoricalData<T>* historical_data_service_; ///< Pointer to historical position data service

public:
    explicit HistPositionListener(PositionHistoricalData<T>* historical_data_service)
        : historical_data_service_(historical_data_service) {}

    void ProcessAdd(Position<T>& data) override {
        if (historical_data_service_) {
            historical_data_service_->PersistData("key", data);
        }
    }

    void ProcessRemove(Position<T>&) override {}
    void ProcessUpdate(Position<T>&) override {}
};

template<typename T>
class HistRiskListener : public ServiceListener<PV01<T>> {
private:
    RiskHistoricalData<T>* risk_historical_service_; ///< Pointer to historical risk data service

public:
    explicit HistRiskListener(RiskHistoricalData<T>* risk_historical_service)
        : risk_historical_service_(risk_historical_service) {}

    void ProcessAdd(PV01<T>& data) override {
        if (risk_historical_service_) {
            risk_historical_service_->PersistData("key", data);
        }
    }

    void ProcessRemove(PV01<T>&) override {}
    void ProcessUpdate(PV01<T>&) override {}
};

template<typename T>
class HistStreamingListener : public ServiceListener<PriceStream<T>> {
private:
    StreamingHistoricalDataService<T>* streaming_historical_service_; ///< Pointer to streaming historical data service

public:
    explicit HistStreamingListener(StreamingHistoricalDataService<T>* streaming_historical_service)
        : streaming_historical_service_(streaming_historical_service) {}

    void ProcessAdd(PriceStream<T>& data) override {
        if (streaming_historical_service_) {
            streaming_historical_service_->PersistData("key", data);
        }
    }

    void ProcessRemove(PriceStream<T>&) override {}
    void ProcessUpdate(PriceStream<T>&) override {}
};

template<typename T>
class GUIListener : public ServiceListener<Price<T>> {
private:
    GUIService<T>* gui_service_; ///< Pointer to GUIService

public:
    explicit GUIListener(GUIService<T>* gui_service)
        : gui_service_(gui_service) {}

    void ProcessAdd(Price<T>& data) override {
        if (gui_service_) {
            gui_service_->SendDataToGUI(data);
        }
    }

    void ProcessRemove(Price<T>&) override {}
    void ProcessUpdate(Price<T>&) override {}
};

template<typename T>
class AlgoStreamingListener : public ServiceListener<Price<T>> {
private:
    BondAlgoStreamingService<T>* algo_streaming_service_; ///< Pointer to BondAlgoStreamingService

public:
    explicit AlgoStreamingListener(BondAlgoStreamingService<T>* algo_streaming_service)
        : algo_streaming_service_(algo_streaming_service) {}

    void ProcessAdd(Price<T>& data) override {
        if (algo_streaming_service_) {
            algo_streaming_service_->PublishPrice(data);
        }
    }

    void ProcessRemove(Price<T>&) override {}
    void ProcessUpdate(Price<T>&) override {}
};

template<typename T>
class StreamingListener : public ServiceListener<PriceStream<T>> {
private:
    StreamingService<T>* streaming_service_; ///< Pointer to StreamingService

public:
    explicit StreamingListener(StreamingService<T>* streaming_service)
        : streaming_service_(streaming_service) {}

    void ProcessAdd(PriceStream<T>& data) override {
        if (streaming_service_) {
            streaming_service_->PublishPrice(data);
        }
    }

    void ProcessRemove(PriceStream<T>&) override {}
    void ProcessUpdate(PriceStream<T>&) override {}
};

template<typename T>
class BondAlgoExecutionListener : public ServiceListener<OrderBook<T>> {
private:
    BondAlgoExecutionService<T>* execution_service_; ///< Pointer to BondAlgoExecutionService

public:
    explicit BondAlgoExecutionListener(BondAlgoExecutionService<T>* execution_service)
        : execution_service_(execution_service) {}

    void ProcessAdd(OrderBook<T>& order_book_data) override {
        if (execution_service_) {
            execution_service_->Execute(order_book_data);
        }
    }

    void ProcessRemove(OrderBook<T>&) override {}
    void ProcessUpdate(OrderBook<T>&) override {}
};

template<typename T>
class ExecutionServiceListener : public ServiceListener<AlgoExecution<T>> {
private:
    ExecutionService<T>* execution_service_; ///< Pointer to ExecutionService

public:
    explicit ExecutionServiceListener(ExecutionService<T>* execution_service)
        : execution_service_(execution_service) {}

    void ProcessAdd(AlgoExecution<T>& algo_execution_data) override {
        if (execution_service_) {
            auto order = algo_execution_data.GetExecutionOrder();
            auto market = algo_execution_data.GetExecutionMarket();
            execution_service_->ExecuteOrder(order, market);
        }
    }

    void ProcessRemove(AlgoExecution<T>&) override {}
    void ProcessUpdate(AlgoExecution<T>&) override {}
};

template<typename T>
class TradeBookingServiceListener : public ServiceListener<ExecutionOrder<T>> {
private:
    TradeBookingService<T>* booking_service_; ///< Pointer to TradeBookingService

public:
    explicit TradeBookingServiceListener(TradeBookingService<T>* booking_service)
        : booking_service_(booking_service) {}

    void ProcessAdd(ExecutionOrder<T>& execution_order_data) override {
        if (booking_service_) {
            T product = execution_order_data.GetProduct();
            std::string order_id = execution_order_data.GetOrderId();
            double price = execution_order_data.GetPrice();

            int id = std::stoi(order_id);
            const std::vector<std::string> books = { "TRSY1", "TRSY2", "TRSY3" };
            std::string book = books[id % books.size()];

            long quantity = execution_order_data.GetVisibleQuantity();
            PricingSide side = execution_order_data.GetPricingSide();
            Side order_side = (side == BID) ? BUY : SELL;

            booking_service_->BookTrade(Trade<T>{product, order_id, price, book, quantity, order_side});
        }
    }

    void ProcessRemove(ExecutionOrder<T>&) override {}
    void ProcessUpdate(ExecutionOrder<T>&) override {}
};

template<typename T>
class ExecutionHistoricalDataServiceListener : public ServiceListener<ExecutionOrder<T>> {
private:
    ExecutionHistoricalService<T>* historical_service_; ///< Pointer to ExecutionHistoricalService

public:
    explicit ExecutionHistoricalDataServiceListener(ExecutionHistoricalService<T>* historical_service)
        : historical_service_(historical_service) {}

    void ProcessAdd(ExecutionOrder<T>& execution_order_data) override {
        if (historical_service_) {
            historical_service_->PersistData("key", execution_order_data);
        }
    }

    void ProcessRemove(ExecutionOrder<T>&) override {}
    void ProcessUpdate(ExecutionOrder<T>&) override {}
};

template<typename T>
class AllInquiryHistoricalDataServiceListener : public ServiceListener<Inquiry<T>> {
private:
    InquiryHistoricalService<T>* inquiry_service_; ///< Pointer to InquiryHistoricalService

public:
    explicit AllInquiryHistoricalDataServiceListener(InquiryHistoricalService<T>* inquiry_service)
        : inquiry_service_(inquiry_service) {}

    void ProcessAdd(Inquiry<T>& inquiry_data) override {
        if (inquiry_service_) {
            inquiry_service_->PersistData("key", inquiry_data);
        }
    }

    void ProcessRemove(Inquiry<T>&) override {}
    void ProcessUpdate(Inquiry<T>&) override {}
};

#endif // LISTENERS_HPP
