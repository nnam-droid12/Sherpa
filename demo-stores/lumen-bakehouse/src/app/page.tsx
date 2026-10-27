import Link from "next/link";
import { products } from "@/lib/products";

export default function Home() {
  return (
    <main>
      <section className="hero">
        <h1>Cakes worth gathering for.</h1>
        <p>Baked to order in small batches. Preorder at least two days ahead for delivery.</p>
      </section>
      <div className="container">
        <div className="cakes">
          {products.map((p) => (
            <article key={p.id} className="cake">
              <Link href={`/cakes/${p.id}`}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={p.image} alt={p.title} />
              </Link>
              <div className="info">
                <h3>
                  <Link href={`/cakes/${p.id}`}>{p.title}</Link>
                </h3>
                <p>
                  <span className="price">${p.price}</span> · serves {p.serves}
                </p>
              </div>
            </article>
          ))}
        </div>
      </div>
    </main>
  );
}
