export type Product = {
  id: string;
  title: string;
  description: string;
  price: string;
  serves: number;
  image: string;
  leadTimeDays: number;
};

export const products: Product[] = [
  {
    id: "vanilla-bean-celebration",
    title: "Vanilla Bean Celebration Cake",
    description: "Three layers of vanilla bean sponge with whipped mascarpone and a hand-piped border.",
    price: "78.00",
    serves: 12,
    image: "/img/vanilla.svg",
    leadTimeDays: 2,
  },
  {
    id: "dark-chocolate-ganache",
    title: "Dark Chocolate Ganache Cake",
    description: "Cocoa sponge, salted caramel and a glossy 70% dark chocolate ganache.",
    price: "96.00",
    serves: 16,
    image: "/img/chocolate.svg",
    leadTimeDays: 2,
  },
  {
    id: "lemon-elderflower",
    title: "Lemon & Elderflower Cake",
    description: "Lemon drizzle sponge, elderflower syrup and lemon curd buttercream.",
    price: "64.00",
    serves: 8,
    image: "/img/lemon.svg",
    leadTimeDays: 2,
  },
  {
    id: "strawberry-shortcake",
    title: "Strawberry Cream Shortcake",
    description: "Light chiffon layers with fresh strawberries and vanilla chantilly cream.",
    price: "72.00",
    serves: 10,
    image: "/img/strawberry.svg",
    leadTimeDays: 2,
  },
  {
    id: "three-tier-celebration",
    title: "Three-Tier Celebration Cake",
    description: "A showpiece tiered cake in your choice of flavours, finished with sugar flowers.",
    price: "245.00",
    serves: 60,
    image: "/img/tiered.svg",
    leadTimeDays: 7,
  },
  {
    id: "morning-bun-box",
    title: "Cardamom Morning Bun Box",
    description: "Six laminated morning buns rolled in cardamom sugar.",
    price: "24.00",
    serves: 6,
    image: "/img/buns.svg",
    leadTimeDays: 1,
  },
];

export function findProduct(id: string) {
  return products.find((p) => p.id === id);
}
