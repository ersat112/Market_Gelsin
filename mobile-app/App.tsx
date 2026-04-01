import { useMemo, useState } from "react";
import {
  Pressable,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View
} from "react-native";

import { MarketSummaryCard } from "./src/components/MarketSummaryCard";
import { RecommendationRow } from "./src/components/RecommendationRow";
import { SectionCard } from "./src/components/SectionCard";
import { cities, markets } from "./src/data/seed";
import { analyzeBasket, getMarketsForCity, getSearchResults, parseShoppingList } from "./src/lib/recommendation";
import { CityId } from "./src/types";
import { theme } from "./src/theme";

const defaultList = ["sut 1 l", "patates", "makarna 500 g", "aycicek yagi 1 l", "normal ekmek"].join("\n");

export default function App() {
  const [selectedCity, setSelectedCity] = useState<CityId>("konya");
  const [searchTerm, setSearchTerm] = useState("sut");
  const [shoppingListInput, setShoppingListInput] = useState(defaultList);

  const searchResults = useMemo(() => getSearchResults(selectedCity, searchTerm), [selectedCity, searchTerm]);
  const shoppingItems = useMemo(() => parseShoppingList(shoppingListInput), [shoppingListInput]);
  const basketAnalysis = useMemo(() => analyzeBasket(selectedCity, shoppingItems), [selectedCity, shoppingItems]);
  const cityMarkets = useMemo(() => getMarketsForCity(selectedCity), [selectedCity]);
  const cityInfo = cities.find((city) => city.id === selectedCity);

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="dark-content" />
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.hero}>
          <Text style={styles.overline}>ErenesAl mobile MVP</Text>
          <Text style={styles.title}>Konuma gore market karsilastirma ve akilli sepet dagitimi</Text>
          <Text style={styles.subtitle}>
            Kullanici sehir bazli online marketleri gorur, urun arar ve alisveris listesini en uygun markete gore parcali
            ya da tek market olarak optimize eder.
          </Text>
        </View>

        <SectionCard
          eyebrow="Lokasyon"
          title="Kullanicinin bulundugu sehri merkez alan akış"
          subtitle={cityInfo?.subtitle}
        >
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.cityRow}>
            {cities.map((city) => (
              <Pressable
                key={city.id}
                onPress={() => setSelectedCity(city.id)}
                style={[styles.cityChip, city.id === selectedCity ? styles.cityChipActive : undefined]}
              >
                <Text style={[styles.cityChipText, city.id === selectedCity ? styles.cityChipTextActive : undefined]}>
                  {city.name}
                </Text>
              </Pressable>
            ))}
          </ScrollView>

          <View style={styles.marketGrid}>
            {cityMarkets.map((market) => (
              <View key={market.id} style={styles.marketPill}>
                <Text style={styles.marketPillName}>{market.name}</Text>
                <Text style={styles.marketPillMeta}>
                  {market.badge} - Teslimat {market.eta}
                </Text>
              </View>
            ))}
          </View>
        </SectionCard>

        <SectionCard
          eyebrow="Urun Arama"
          title="Secili sehirde urun bazli fiyat karsilastirma"
          subtitle="Bu bolum tek urun aramada hangi markette en iyi fiyat oldugunu gosterir."
        >
          <TextInput
            value={searchTerm}
            onChangeText={setSearchTerm}
            placeholder="Ornek: sut, patates, makarna"
            placeholderTextColor={theme.colors.textMuted}
            style={styles.input}
          />

          {searchResults.length === 0 ? (
            <Text style={styles.emptyState}>Aranan urun icin bu sehirde eslesen sonuc bulunamadi.</Text>
          ) : (
            <View style={styles.resultStack}>
              {searchResults.slice(0, 5).map((entry) => {
                const market = markets.find((item) => item.id === entry.marketId);

                return (
                  <View key={entry.id} style={styles.resultCard}>
                    <View style={styles.resultHead}>
                      <Text style={styles.resultName}>{entry.productName}</Text>
                      <Text style={styles.resultPrice}>{entry.price.toFixed(2)} TL</Text>
                    </View>
                    <Text style={styles.resultMeta}>
                      {market?.name} - {entry.category} - {entry.freshnessLabel}
                    </Text>
                  </View>
                );
              })}
            </View>
          )}
        </SectionCard>

        <SectionCard
          eyebrow="Akilli Liste"
          title="Alisveris listesini yukle, en uygun sepet dagitimini gor"
          subtitle="MVP asamasinda dosya import yerine liste metin olarak yapistiriliyor. Sonraki iterasyonda dosya yukleme ve OCR eklenebilir."
        >
          <TextInput
            multiline
            numberOfLines={6}
            value={shoppingListInput}
            onChangeText={setShoppingListInput}
            placeholder="Her satira bir urun yaz"
            placeholderTextColor={theme.colors.textMuted}
            style={[styles.input, styles.textArea]}
          />

          <View style={styles.summaryPanel}>
            <View style={styles.metricCard}>
              <Text style={styles.metricLabel}>Bolunmus sepet toplam</Text>
              <Text style={styles.metricValue}>{basketAnalysis.splitBasketTotal.toFixed(2)} TL</Text>
            </View>
            <View style={styles.metricCard}>
              <Text style={styles.metricLabel}>En iyi tek market</Text>
              <Text style={styles.metricValue}>{basketAnalysis.bestSingleMarket?.marketName ?? "Yok"}</Text>
            </View>
          </View>

          <View style={styles.recommendationStack}>
            {basketAnalysis.productRecommendations.map((recommendation) => (
              <RecommendationRow key={recommendation.requestedItem} recommendation={recommendation} />
            ))}
          </View>
        </SectionCard>

        <SectionCard
          eyebrow="Sepet Stratejisi"
          title="Tek market mi, parcali alim mi?"
          subtitle="Kullanici isterse tum listeyi tek markette tamamlar, isterse urun bazli en ucuz marketlere boler."
        >
          {basketAnalysis.marketTotals.map((summary, index) => (
            <MarketSummaryCard
              key={summary.marketId}
              summary={summary}
              highlight={basketAnalysis.bestSingleMarket?.marketId === summary.marketId && index === 0}
            />
          ))}
        </SectionCard>

        <SectionCard
          eyebrow="Sonraki Adim"
          title="Bu MVP'yi gercek APK urunune donusturme plani"
          subtitle="Buradaki ekran akisi seed veri ile calisiyor. Bir sonraki adimda Python scraper ciktilari API uzerinden bu mobil istemciye beslenecek."
        >
          <Text style={styles.roadmapItem}>1. Scraper verisini normalize eden API katmani kurulacak.</Text>
          <Text style={styles.roadmapItem}>2. Cihaz konumu ile sehir otomatik secilecek.</Text>
          <Text style={styles.roadmapItem}>3. Alisveris listesi dosya yukleme, sesli giris ve OCR destekleyecek.</Text>
          <Text style={styles.roadmapItem}>4. EAS ile Android APK preview build alinacak.</Text>
        </SectionCard>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    backgroundColor: theme.colors.background,
    flex: 1
  },
  content: {
    gap: theme.spacing.lg,
    padding: theme.spacing.lg,
    paddingBottom: 60
  },
  hero: {
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.lg,
    gap: theme.spacing.sm,
    padding: theme.spacing.xl
  },
  overline: {
    color: "#D5E5DB",
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1.4,
    textTransform: "uppercase"
  },
  title: {
    color: "#FFF8ED",
    fontSize: 31,
    fontWeight: "900",
    lineHeight: 38
  },
  subtitle: {
    color: "#E9F0EB",
    fontSize: 15,
    lineHeight: 22
  },
  cityRow: {
    gap: theme.spacing.sm
  },
  cityChip: {
    backgroundColor: theme.colors.surfaceMuted,
    borderRadius: 999,
    paddingHorizontal: 16,
    paddingVertical: 10
  },
  cityChipActive: {
    backgroundColor: theme.colors.primary
  },
  cityChipText: {
    color: theme.colors.text,
    fontSize: 14,
    fontWeight: "700"
  },
  cityChipTextActive: {
    color: "#FFFDF8"
  },
  marketGrid: {
    gap: theme.spacing.sm
  },
  marketPill: {
    backgroundColor: theme.colors.surfaceMuted,
    borderRadius: theme.radius.md,
    gap: 2,
    padding: theme.spacing.md
  },
  marketPillName: {
    color: theme.colors.text,
    fontSize: 15,
    fontWeight: "800"
  },
  marketPillMeta: {
    color: theme.colors.textMuted,
    fontSize: 13
  },
  input: {
    backgroundColor: "#FFFCF5",
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    color: theme.colors.text,
    fontSize: 15,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: 14
  },
  textArea: {
    minHeight: 140,
    textAlignVertical: "top"
  },
  emptyState: {
    color: theme.colors.textMuted,
    fontSize: 14,
    lineHeight: 20
  },
  resultStack: {
    gap: theme.spacing.sm
  },
  resultCard: {
    backgroundColor: "#FFFCF5",
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    gap: 6,
    padding: theme.spacing.md
  },
  resultHead: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between"
  },
  resultName: {
    color: theme.colors.text,
    flex: 1,
    fontSize: 15,
    fontWeight: "700",
    paddingRight: theme.spacing.sm
  },
  resultPrice: {
    color: theme.colors.accent,
    fontSize: 16,
    fontWeight: "900"
  },
  resultMeta: {
    color: theme.colors.textMuted,
    fontSize: 13
  },
  summaryPanel: {
    flexDirection: "row",
    gap: theme.spacing.sm
  },
  metricCard: {
    backgroundColor: theme.colors.primarySoft,
    borderRadius: theme.radius.md,
    flex: 1,
    gap: 6,
    padding: theme.spacing.md
  },
  metricLabel: {
    color: theme.colors.textMuted,
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase"
  },
  metricValue: {
    color: theme.colors.primary,
    fontSize: 18,
    fontWeight: "900"
  },
  recommendationStack: {
    gap: theme.spacing.md
  },
  roadmapItem: {
    color: theme.colors.text,
    fontSize: 14,
    lineHeight: 20
  }
});
