export interface BuyerProfile {
  email: string;
  firstName: string;
  lastName: string;
  address1: string;
  city: string;
  province: string;
  postalCode: string;
  countryLabel: string;
  phone: string;
}

export const PRODUCT = Object.freeze({
  path: "/products/t-shirt",
  title: "Medusa T-Shirt",
  catalogLinkLabel: "Medusa T-Shirt \u2192",
  variantLabel: "M / Black \u2014 M / Black EUR 10",
  shippingLabel: "Standard Shipping EUR 10",
  paymentLabel: "System / manual demo payment",
});

const BUYERS: Readonly<Record<string, BuyerProfile>> = Object.freeze({
  "desktop-chromium": Object.freeze({
    email: "routedeck-e2e-desktop@example.com",
    firstName: "RouteDeck",
    lastName: "Desktop",
    address1: "1 Test Street",
    city: "London",
    province: "Greater London",
    postalCode: "SW1A 1AA",
    countryLabel: "GB",
    phone: "+442079460001",
  }),
  "mobile-chromium": Object.freeze({
    email: "routedeck-e2e-mobile@example.com",
    firstName: "RouteDeck",
    lastName: "Mobile",
    address1: "2 Test Street",
    city: "London",
    province: "Greater London",
    postalCode: "SW1A 1AA",
    countryLabel: "GB",
    phone: "+442079460002",
  }),
});

export function buyerForProject(projectName: string): BuyerProfile {
  const buyer = BUYERS[projectName];
  if (buyer === undefined) {
    throw new Error(`No explicit buyer profile is declared for ${projectName}.`);
  }
  return buyer;
}
