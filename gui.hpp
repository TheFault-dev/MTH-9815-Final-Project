#ifndef GUI_SERVICE_HPP
#define GUI_SERVICE_HPP

#include <chrono>
#include <fstream>
#include <iostream>
#include <string>
#include <tuple>
#include <unordered_map>

#include "connectors.hpp"
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

template<typename T>
class GUIService : public Service<string, Price<T>> {
private:
    static constexpr long long update_interval = 300;  // Update interval in ms
    long long start_time;      // Service initialization time
    long long last_update;     // Last GUI update time
    GUIConnector<T>* gui_connector;  // GUI connector pointer

public:
    explicit GUIService(GUIConnector<T>* connector)
        : gui_connector(connector) {
        start_time = get_current_time();
        last_update = start_time;
    }

    // Send price data to GUI with throttling based on update interval
    void SendDataToGUI(Price<T> price_data) {
        long long current_time = get_current_time();

        if ((current_time - last_update) > update_interval) {
            last_update = current_time;
            gui_connector->Publish(price_data);
        }
    }

private:
    // Get current time in milliseconds since epoch
    long long get_current_time() const {
        return duration_cast<milliseconds>(system_clock::now().time_since_epoch()).count();
    }
};

#endif
