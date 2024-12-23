//  MTH 9815 Final Project
//
//  Created by Ruida Huang on 12/20/24.
//

#ifndef PRODUCTMAP_HPP
#define PRODUCTMAP_HPP

#include <vector>
#include <unordered_map>
#include "products.hpp"
class ProductMap
{
public:
    static unordered_map<string, Bond> GetProductMap()
    {
        std::unordered_map<string, Bond> product_map;
        vector<Bond> bonds;
        bonds.emplace_back( Bond("T02Y", CUSIP, "T02Y", 0.04, date(2026,12,21)));
        bonds.emplace_back( Bond("T03Y", CUSIP, "T03Y", 0.04, date(2027,12,21)));
        bonds.emplace_back( Bond("T05Y", CUSIP, "T05Y", 0.04, date(2029,12,21)));
        bonds.emplace_back( Bond("T07Y", CUSIP, "T07Y", 0.04, date(2031,12,21)));
        bonds.emplace_back( Bond("T10Y", CUSIP, "T10Y", 0.04, date(2034,12,21)));
        bonds.emplace_back( Bond("T20Y", CUSIP, "T20Y", 0.04, date(2044,12,21)));
        bonds.emplace_back( Bond("T30Y", CUSIP, "T30Y", 0.04, date(2054,12,21)));
        
        for (auto bond: bonds)
        {
            auto pair=make_pair(bond.GetProductId(),bond);
            product_map.insert(pair);
        }
        return product_map;
    }
    
    static vector<Bond> GetProducts(){
        vector<Bond> bonds;
        bonds.emplace_back( Bond("T02Y", CUSIP, "T02Y", 0.04, date(2026,12,21)));
        bonds.emplace_back( Bond("T03Y", CUSIP, "T03Y", 0.04, date(2027,12,21)));
        bonds.emplace_back( Bond("T05Y", CUSIP, "T05Y", 0.04, date(2029,12,21)));
        bonds.emplace_back( Bond("T07Y", CUSIP, "T06Y", 0.04, date(2031,12,21)));
        bonds.emplace_back( Bond("T10Y", CUSIP, "T10Y", 0.04, date(2034,12,21)));
        bonds.emplace_back( Bond("T20Y", CUSIP, "T20Y", 0.04, date(2044,12,21)));
        bonds.emplace_back( Bond("T30Y", CUSIP, "T30Y", 0.04, date(2054,12,21)));
        return bonds;
    }
    
    static vector<string> GetTickers()
    {
        return vector<string>{"T02Y", "T03Y", "T05Y", "T07Y", "T10Y", "T20Y", "T30Y"};
    }
};

#endif
