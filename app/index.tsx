import React, { useCallback } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createDrawerNavigator, DrawerScreenProps } from '@react-navigation/drawer';
import { Linking, SafeAreaView, StyleSheet, View } from 'react-native';
import LinkButton from './components/LinkButton';
import LinkOpenerScreen from './screens/LinkOpenerScreen';
import TextContentScreen from './screens/TextContentScreen';

type RootDrawerParamList = {
  Home: undefined;
  Privacy: undefined;
  'Our Apps': undefined;
  Telegram: undefined;
  'Naksir Website': undefined;
  Legal: undefined;
  Terms: undefined;
  '2+ Odds': undefined;
  '3+ Odds': undefined;
  '4+ Odds': undefined;
  'Stake Strategy': undefined;
};

const Drawer = createDrawerNavigator<RootDrawerParamList>();

const PRIVACY_URL = 'https://naksirpredictions.top/privacy-policy';
const OUR_APPS_URL = 'https://play.google.com/store/apps/dev?id=6165954326742483653';
const TELEGRAM_URL = 'https://t.me/naksiranalysis';
const NAKSIR_WEBSITE_URL = 'https://naksirpredictions.top';

type HomeProps = DrawerScreenProps<RootDrawerParamList, 'Home'>;

const HomeScreen: React.FC<HomeProps> = ({ navigation }) => {
  const openLink = useCallback(async (url: string) => {
    const supported = await Linking.canOpenURL(url);
    if (supported) {
      await Linking.openURL(url);
    }
  }, []);

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.topButtons}>
        <LinkButton
          label="Privacy"
          variant="secondary"
          onPress={() => openLink(PRIVACY_URL)}
        />
        <LinkButton
          label="Legal"
          variant="secondary"
          onPress={() => navigation.navigate('Legal')}
        />
        <LinkButton
          label="Terms"
          variant="secondary"
          onPress={() => navigation.navigate('Terms')}
        />
      </View>
      <View style={styles.bottomButtons}>
        <LinkButton label="2+ Odds" onPress={() => navigation.navigate('2+ Odds')} />
        <LinkButton label="3+ Odds" onPress={() => navigation.navigate('3+ Odds')} />
        <LinkButton label="4+ Odds" onPress={() => navigation.navigate('4+ Odds')} />
        <LinkButton
          label="TELEGRAM"
          onPress={() => openLink(TELEGRAM_URL)}
          style={styles.telegramButton}
        />
        <LinkButton
          label="STAKE STRATEGY THEORY"
          onPress={() => navigation.navigate('Stake Strategy')}
        />
      </View>
    </SafeAreaView>
  );
};

const LegalScreen = () => (
  <TextContentScreen
    title="Legal"
    body={[
      'All content provided through the Focus Bets feed is intended for informational purposes only.',
      'Regulatory obligations, betting restrictions, and compliance remain the full responsibility of each individual user.',
      'By using this application you acknowledge that you are solely accountable for adhering to the legal framework applicable in your jurisdiction.'
    ]}
  />
);

const TermsScreen = () => (
  <TextContentScreen
    title="Terms & Conditions"
    body={[
      'Selections shared in this feed are curated algorithmically and may not guarantee any particular outcome.',
      'You agree not to resell or redistribute the information without explicit permission from Naksir Predictions.',
      'Always stake responsibly and only wager what you can afford to lose.'
    ]}
  />
);

const OddsScreenFactory = (title: '2+ Odds' | '3+ Odds' | '4+ Odds') => () => (
  <TextContentScreen
    title={title}
    body={[
      `${title} suggestions update dynamically based on the latest data feed.`,
      'Monitor the drawer for the freshest picks and keep notifications enabled to react quickly.',
      'Tap any selection to reveal further statistical context and confidence markers when available.'
    ]}
  />
);

const StakeStrategyScreen = () => (
  <TextContentScreen
    title="Stake Strategy Theory"
    body={[
      'Balance your bankroll by allocating a fixed percentage per ticket and avoid chasing losses.',
      'Diversify stakes between confidence tiers: conservative on 2+ odds, moderate on 3+, and carefully measured exposure on 4+.',
      'Reassess limits weekly and document every bet to evaluate performance and keep the approach disciplined.'
    ]}
  />
);

const App: React.FC = () => (
  <NavigationContainer>
    <Drawer.Navigator
      initialRouteName="Home"
      screenOptions={{
        headerStyle: { backgroundColor: '#0f172a' },
        headerTintColor: '#f1f5f9',
        drawerActiveTintColor: '#1f2937',
        drawerLabelStyle: { fontSize: 16 },
      }}
    >
      <Drawer.Screen name="Home" component={HomeScreen} options={{ title: 'Dashboard' }} />
      <Drawer.Screen name="Privacy" options={{ title: 'Privacy Policy' }}>
        {() => <LinkOpenerScreen url={PRIVACY_URL} label="Privacy Policy" />}
      </Drawer.Screen>
      <Drawer.Screen name="Our Apps" options={{ title: 'Our Apps' }}>
        {() => <LinkOpenerScreen url={OUR_APPS_URL} label="Google Play Store" />}
      </Drawer.Screen>
      <Drawer.Screen name="Telegram" options={{ title: 'Telegram Channel' }}>
        {() => <LinkOpenerScreen url={TELEGRAM_URL} label="Telegram" />}
      </Drawer.Screen>
      <Drawer.Screen name="Naksir Website" options={{ title: 'Naksir Website' }}>
        {() => <LinkOpenerScreen url={NAKSIR_WEBSITE_URL} label="Naksir Predictions" />}
      </Drawer.Screen>
      <Drawer.Screen name="Legal" component={LegalScreen} />
      <Drawer.Screen name="Terms" component={TermsScreen} />
      <Drawer.Screen name="2+ Odds" component={OddsScreenFactory('2+ Odds')} />
      <Drawer.Screen name="3+ Odds" component={OddsScreenFactory('3+ Odds')} />
      <Drawer.Screen name="4+ Odds" component={OddsScreenFactory('4+ Odds')} />
      <Drawer.Screen
        name="Stake Strategy"
        component={StakeStrategyScreen}
        options={{ title: 'Stake Strategy Theory' }}
      />
    </Drawer.Navigator>
  </NavigationContainer>
);

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#020617',
    paddingHorizontal: 20,
    paddingVertical: 24,
  },
  topButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
  },
  bottomButtons: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  telegramButton: {
    backgroundColor: '#229ED9',
  },
});

export default App;
