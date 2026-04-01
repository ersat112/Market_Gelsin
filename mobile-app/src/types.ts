export type CityId = "konya" | "ankara" | "istanbul";

export type Market = {
  id: string;
  name: string;
  cityId: CityId;
  badge: string;
  eta: string;
};

export type PriceEntry = {
  id: string;
  cityId: CityId;
  marketId: string;
  productName: string;
  category: string;
  price: number;
  unit: string;
  freshnessLabel: string;
};

export type ProductRecommendation = {
  requestedItem: string;
  found: boolean;
  bestOption?: PriceEntry;
  options: PriceEntry[];
};

export type MarketBasketSummary = {
  marketId: string;
  marketName: string;
  matchedItems: number;
  missingItems: string[];
  total: number;
};

export type BasketAnalysis = {
  requestedItems: string[];
  productRecommendations: ProductRecommendation[];
  splitBasketTotal: number;
  bestSingleMarket?: MarketBasketSummary;
  marketTotals: MarketBasketSummary[];
};
