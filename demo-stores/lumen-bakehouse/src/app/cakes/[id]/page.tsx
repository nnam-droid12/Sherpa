import { notFound } from "next/navigation";
import { AddToCart } from "@/components/add-to-cart";
import { findProduct, products } from "@/lib/products";

export function generateStaticParams() {
  return products.map((p) => ({ id: p.id }));
}

export default async function CakePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const product = findProduct(id);
  if (!product) notFound();
  return (
    <main className="container">
      <div className="detail">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={product.image} alt={product.title} />
        <div>
          <h1>{product.title}</h1>
          <p className="price">${product.price}</p>
          <p>{product.description}</p>
          <p>
            Serves {product.serves} · Order {product.leadTimeDays} day{product.leadTimeDays > 1 ? "s" : ""} ahead
          </p>
          <AddToCart product={product} />
        </div>
      </div>
    </main>
  );
}
