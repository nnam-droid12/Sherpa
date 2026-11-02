export type Product = {
  id: string;
  title: string;
  description: string;
  price: string;
  serves: number;
  image: string;
  leadTimeDays: number;
  rating: number;
  reviews: number;
  badge?: string;
  flavours: string[];
};

export const products: Product[] = [
  {
    id: "vanilla-bean-celebration",
    title: "Vanilla Bean Celebration Cake",
    description:
      "Three layers of vanilla bean sponge with whipped mascarpone, piped cream rosettes and a fresh berry crown. Our most-ordered birthday cake.",
    price: "78.00",
    serves: 12,
    image: "/img/vanilla-bean-celebration.jpg",
    leadTimeDays: 2,
    rating: 4.9,
    reviews: 318,
    badge: "Birthday favourite",
    flavours: ["Vanilla bean", "Mascarpone cream", "Seasonal berries"],
  },
  {
    id: "dark-chocolate-ganache",
    title: "Dark Chocolate Layer Cake",
    description:
      "Four layers of cocoa sponge with salted caramel, finished in a glossy 70% dark chocolate ganache. Rich, deep and made for sharing.",
    price: "96.00",
    serves: 16,
    image: "/img/dark-chocolate-ganache.jpg",
    leadTimeDays: 2,
    rating: 4.8,
    reviews: 204,
    flavours: ["70% dark chocolate", "Salted caramel", "Cocoa sponge"],
  },
  {
    id: "lemon-elderflower",
    title: "Lemon & Elderflower Bundt",
    description:
      "A tender lemon drizzle bundt soaked in elderflower syrup and finished with a sharp lemon glaze. Bright, light and perfect with tea.",
    price: "64.00",
    serves: 8,
    image: "/img/lemon-elderflower.jpg",
    leadTimeDays: 2,
    rating: 4.7,
    reviews: 126,
    flavours: ["Lemon", "Elderflower", "Lemon glaze"],
  },
  {
    id: "strawberry-shortcake",
    title: "Strawberry Cream Tart",
    description:
      "Crisp sweet pastry filled with vanilla crème pâtissière and piled high with fresh strawberries and blueberries.",
    price: "72.00",
    serves: 10,
    image: "/img/strawberry-shortcake.jpg",
    leadTimeDays: 2,
    rating: 4.8,
    reviews: 152,
    badge: "Seasonal",
    flavours: ["Strawberry", "Vanilla crème pâtissière", "Sweet pastry"],
  },
  {
    id: "three-tier-celebration",
    title: "Three-Tier Celebration Cake",
    description:
      "A showpiece tiered cake in your choice of flavours, wrapped in fluted buttercream and crowned with handmade sugar roses. Weddings, milestones, big days.",
    price: "245.00",
    serves: 60,
    image: "/img/three-tier-celebration.jpg",
    leadTimeDays: 7,
    rating: 5.0,
    reviews: 64,
    badge: "Made to order",
    flavours: ["Choose up to three flavours", "Sugar roses", "Fluted buttercream"],
  },
  {
    id: "morning-bun-box",
    title: "Cinnamon Morning Bun Box",
    description:
      "Six soft, laminated cinnamon buns with a brown-sugar swirl and vanilla glaze, baked the morning they're delivered.",
    price: "24.00",
    serves: 6,
    image: "/img/morning-bun-box.jpg",
    leadTimeDays: 1,
    rating: 4.9,
    reviews: 411,
    flavours: ["Cinnamon sugar", "Vanilla glaze"],
  },
];

export function findProduct(id: string) {
  return products.find((p) => p.id === id);
}
