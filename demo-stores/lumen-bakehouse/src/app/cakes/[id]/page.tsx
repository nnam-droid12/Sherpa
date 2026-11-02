import Link from "next/link";
import { notFound } from "next/navigation";
import { AddToCart } from "@/components/add-to-cart";
import { Stars } from "@/components/stars";
import { findProduct, products } from "@/lib/products";

export function generateStaticParams() {
  return products.map((p) => ({ id: p.id }));
}

export default async function CakePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const product = findProduct(id);
  if (!product) notFound();
  const others = products.filter((p) => p.id !== product.id).slice(0, 3);
  return (
    <main className="container">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link href="/">Home</Link> / <Link href="/#cakes">Cakes</Link> / {product.title}
      </nav>
      <div className="detail">
        <div className="detail-media">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={product.image} alt={product.title} />
        </div>
        <div>
          {product.badge && <p className="eyebrow">{product.badge}</p>}
          <h1>{product.title}</h1>
          <Stars rating={product.rating} reviews={product.reviews} />
          <span className="price">${product.price}</span>
          <p>{product.description}</p>
          <div className="facts">
            <div>
              <strong>{product.serves}</strong>
              <span>servings</span>
            </div>
            <div>
              <strong>
                {product.leadTimeDays} day{product.leadTimeDays > 1 ? "s" : ""}
              </strong>
              <span>notice</span>
            </div>
            <div>
              <strong>Free</strong>
              <span>delivery over $60</span>
            </div>
          </div>
          <div className="chips">
            {product.flavours.map((f) => (
              <span key={f}>{f}</span>
            ))}
          </div>
          <AddToCart product={product} />
        </div>
      </div>

      <section style={{ marginTop: 56 }}>
        <div className="section-head">
          <h2>You may also love</h2>
        </div>
        <div className="cakes">
          {others.map((p) => (
            <Link key={p.id} href={`/cakes/${p.id}`} className="cake">
              <div className="cake-media">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={p.image} alt={p.title} loading="lazy" />
              </div>
              <h3>{p.title}</h3>
              <div className="meta">
                <span className="price">${p.price}</span>
                <Stars rating={p.rating} reviews={p.reviews} />
              </div>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
