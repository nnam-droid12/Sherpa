import Link from "next/link";
import { Stars } from "@/components/stars";
import { products } from "@/lib/products";

export default function Home() {
  return (
    <main>
      <section className="hero">
        <div>
          <p className="eyebrow">San Francisco · Baked to order</p>
          <h1>Cakes worth gathering for.</h1>
          <p>
            Small-batch celebration cakes, fruit tarts and morning buns, baked the day before your party and delivered
            to your door.
          </p>
          <div className="hero-actions">
            <Link href="#cakes" className="button">
              Order a cake
            </Link>
            <Link href="#how" className="button ghost">
              How ordering works
            </Link>
          </div>
          <div className="trust">
            <span>
              <strong>4.9★</strong> from 1,200+ reviews
            </span>
            <span>
              <strong>48h</strong> lead time on most cakes
            </span>
            <span>
              <strong>Free</strong> delivery over $60
            </span>
          </div>
        </div>
        <div className="hero-media">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/img/hero.jpg" alt="A white layer cake with a slice cut to show its layers" />
        </div>
      </section>

      <section className="container" id="cakes">
        <div className="section-head">
          <div>
            <p className="eyebrow">This week&apos;s menu</p>
            <h2>Celebration cakes &amp; bakes</h2>
          </div>
          <span className="muted">{products.length} items</span>
        </div>
        <div className="cakes">
          {products.map((p) => (
            <Link key={p.id} href={`/cakes/${p.id}`} className="cake">
              <div className="cake-media">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={p.image} alt={p.title} loading="lazy" />
                {p.badge && <span className="badge">{p.badge}</span>}
              </div>
              <h3>{p.title}</h3>
              <div className="meta">
                <span>
                  <span className="price">${p.price}</span> · serves {p.serves}
                </span>
                <Stars rating={p.rating} reviews={p.reviews} />
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="container" id="how">
        <div className="section-head">
          <div>
            <p className="eyebrow">How ordering works</p>
            <h2>Fresh, never frozen</h2>
          </div>
        </div>
        <div className="steps-grid">
          <div className="step-card">
            <b>1</b>
            <h3>Choose your cake</h3>
            <p>Pick a cake and how many it should serve. Most cakes need two days&apos; notice.</p>
          </div>
          <div className="step-card">
            <b>2</b>
            <h3>Pick a delivery day</h3>
            <p>We bake the day before and deliver anywhere in San Francisco between 9am and 6pm.</p>
          </div>
          <div className="step-card">
            <b>3</b>
            <h3>Celebrate</h3>
            <p>Every cake arrives boxed, chilled and ready to slice, with candles on request.</p>
          </div>
        </div>
      </section>
    </main>
  );
}
