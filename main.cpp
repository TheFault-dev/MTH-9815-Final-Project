//
//  main.cpp
//  MTH 9815 Final Project
//
//  Created by Ruida Huang on 12/20/24.
//

#include<iostream>
#include "BondAlgoExecutionService.hpp"
#include "connectors.hpp"
#include "gui.hpp"
#include "listeners.hpp"
#include "executionservice.hpp"
#include "historicaldataservice.hpp"
#include "inquiryservice.hpp"
#include "positionservice.hpp"
#include "pricingservice.hpp"
#include "products.hpp"
#include "riskservice.hpp"
#include "soa.hpp"
#include "tradebookingservice.hpp"

using namespace std;

int main() {
    // Announce the start of the trading system test
    cout << "Start testing treasury bond trading system." << endl;

    // Initialize Trade Booking Service and its dependent components
    TradeBookingService<Bond> trade_booking_service_instance;
    
    PositionService<Bond> position_service_instance;
    PositionServiceListener<Bond> position_service_listener_instance(&position_service_instance);
    trade_booking_service_instance.AddListener(&position_service_listener_instance); // Link Trade Booking Service to Position Service
    
    PositionConnector<Bond> position_connector_instance("positions.txt");
    PositionHistoricalData<Bond> position_historical_data_instance(&position_connector_instance);
    HistPositionListener<Bond> hist_position_listener_instance(&position_historical_data_instance);
    position_service_instance.AddListener(&hist_position_listener_instance); // Link Position Service to Position History
    
    RiskService<Bond> risk_service_instance;
    RiskServiceListener<Bond> risk_service_listener_instance(&risk_service_instance);
    position_service_instance.AddListener(&risk_service_listener_instance); // Link Position Service to Risk Service
    
    RiskConnector<Bond> risk_connector_instance("risk.txt");
    RiskHistoricalData<Bond> risk_historical_data_instance(&risk_connector_instance);
    HistRiskListener<Bond> hist_risk_listener_instance(&risk_historical_data_instance);
    risk_service_instance.AddListener(&hist_risk_listener_instance); // Link Risk Service to Risk History

    // Load and process trades from the input file
    TradeBookingConnector<Bond> trade_booking_connector_instance("input/trades.txt", &trade_booking_service_instance);
    trade_booking_connector_instance.TraverseTrades();

    // Initialize GUI Service and connect it to Pricing Service
    GUIConnector<Bond> gui_connector_instance("gui.txt");
    GUIService<Bond> gui_service_instance(&gui_connector_instance);
    GUIListener<Bond> gui_listener_instance(&gui_service_instance);
    
    PricingService<Bond> pricing_service_instance;
    pricing_service_instance.AddListener(&gui_listener_instance); // Link Pricing Service to GUI Service
    
    BondAlgoStreamingService<Bond> bond_algo_streaming_service_instance;
    AlgoStreamingListener<Bond> algo_streaming_listener_instance(&bond_algo_streaming_service_instance);
    pricing_service_instance.AddListener(&algo_streaming_listener_instance); // Link Pricing Service to Algo Streaming Service
    
    StreamingService<Bond> streaming_service_instance;
    StreamingListener<Bond> streaming_listener_instance(&streaming_service_instance);
    bond_algo_streaming_service_instance.AddListener(&streaming_listener_instance); // Link Algo Streaming Service to Streaming Service
    
    StreamingConnector<Bond> streaming_connector_instance("streaming.txt");
    StreamingHistoricalDataService<Bond> streaming_historical_data_service_instance(&streaming_connector_instance);
    HistStreamingListener<Bond> hist_streaming_listener_instance(&streaming_historical_data_service_instance);
    streaming_service_instance.AddListener(&hist_streaming_listener_instance); // Link Streaming Service to Historical Streaming Data

    PricingConnector<Bond> pricing_connector_instance("input/prices.txt", &pricing_service_instance);
    pricing_connector_instance.Subscribe(); // Subscribe to Pricing Data

    // Set up Execution and Market Data Services
    BondAlgoExecutionService<Bond> bond_algo_execution_service_instance;
    BondAlgoExecutionListener<Bond> bond_algo_execution_listener_instance(&bond_algo_execution_service_instance);
    
    MarketDataService<Bond> market_data_service_instance;
    market_data_service_instance.AddListener(&bond_algo_execution_listener_instance); // Link Market Data Service to Algo Execution Service
    
    ExecutionService<Bond> execution_service_instance;
    ExecutionServiceListener<Bond> execution_service_listener_instance(&execution_service_instance);
    bond_algo_execution_service_instance.AddListener(&execution_service_listener_instance); // Link Algo Execution Service to Execution Service

    // Initialize Historical Services for Execution and Positions
    ExecutionConnector<Bond> execution_connector_instance("executions.txt");
    ExecutionHistoricalService<Bond> execution_historical_service_instance(&execution_connector_instance);
    ExecutionHistoricalDataServiceListener<Bond> execution_historical_service_listener_instance(&execution_historical_service_instance);
    execution_service_instance.AddListener(&execution_historical_service_listener_instance); // Link Execution Service to Historical Execution Data
    
    MarketDataConnector<Bond> market_data_connector_instance("input/marketdata.txt", &market_data_service_instance);
    market_data_connector_instance.Subscribe(); // Subscribe to Market Data

    // Set up Inquiry Service and Historical Data
    AllInquiriesConnector<Bond> all_inquiries_connector_instance("allinquiries.txt");
    InquiryHistoricalService<Bond> inquiry_historical_service_instance(&all_inquiries_connector_instance);
    AllInquiryHistoricalDataServiceListener<Bond> all_inquiry_historical_listener_instance(&inquiry_historical_service_instance);
    
    InquiryService<Bond> inquiry_service_instance;
    inquiry_service_instance.AddListener(&all_inquiry_historical_listener_instance); // Link Inquiry Service to Historical Inquiry Data
    
    InquiryConnector<Bond> inquiry_connector_instance("input/inquiries.txt", &inquiry_service_instance);
    inquiry_connector_instance.Subscribe(); // Subscribe to Inquiries

    // Announce the end of the trading system test
    cout << "End of the Program" << endl;

    return 0;
}
