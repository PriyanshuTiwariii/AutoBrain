/**
 * Animated illustration of a generic electric car on the landing page. It is deliberately not any maker's model:
 * a photo or likeness of a real car would imply a recommendation and raise image-licensing questions.
 * Pure SVG and CSS (see globals.css), no images to load. Animation stops for people who prefer reduced motion.
 */
export default function HeroCar() {
  return (
    <div
      role="img"
      aria-label="Illustration of an electric car driving along a road"
      className="hero-scene relative w-full overflow-hidden rounded-[22px] border border-sky-line bg-gradient-to-b from-[#CFE6F2] via-sky to-[#F3F8FA]"
    >
      <svg viewBox="0 0 640 260" className="block h-auto w-full" aria-hidden="true">
        <defs>
          <linearGradient id="body" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#1B7FAE" />
            <stop offset="1" stopColor="#0B5F87" />
          </linearGradient>
          <linearGradient id="glass" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#E9F6FC" />
            <stop offset="1" stopColor="#9CCBE0" />
          </linearGradient>
        </defs>

        <circle className="hero-sun" cx="540" cy="62" r="30" fill="#FFD66B" opacity="0.9" />

        <g className="hero-hills" fill="#B7D6E5">
          <path d="M0 170 Q70 110 150 160 T300 150 T470 165 T640 140 V200 H0 Z" />
        </g>
        <g className="hero-hills-near" fill="#9CC4D8">
          <path d="M0 190 Q90 150 180 185 T360 178 T540 190 T640 172 V210 H0 Z" />
        </g>

        <rect x="0" y="198" width="640" height="62" fill="#33444F" />
        <rect x="0" y="198" width="640" height="4" fill="#4A5B66" />
        <g className="hero-road-lines" fill="#F3F5F6">
          {Array.from({ length: 12 }, (_, i) => (
            <rect key={i} x={i * 80} y="228" width="44" height="5" rx="2.5" />
          ))}
        </g>

        <g className="hero-car">
          <ellipse cx="320" cy="212" rx="150" ry="9" fill="#0F1B24" opacity="0.25" />
          <path
            d="M150 196 L150 170 Q150 156 166 152 L232 140 Q262 100 316 98 L372 98 Q414 100 436 138 L484 146 Q500 150 500 168 L500 196 Z"
            fill="url(#body)"
          />
          <path d="M252 140 Q272 110 316 108 L330 108 L330 140 Z" fill="url(#glass)" />
          <path d="M342 108 L372 108 Q402 112 418 140 L342 140 Z" fill="url(#glass)" />
          <rect x="333" y="108" width="6" height="32" fill="#0B5F87" />
          <path d="M150 178 L500 178" stroke="#08445F" strokeWidth="2" opacity="0.5" />
          <rect x="480" y="160" width="20" height="9" rx="4" fill="#FFF3C2" />
          <rect x="150" y="160" width="14" height="9" rx="4" fill="#E8603C" />
          <g className="hero-bolt" transform="translate(386 150)">
            <path d="M10 0 L0 16 H8 L5 28 L18 10 H10 Z" fill="#FFD66B" />
          </g>
          {[212, 440].map((cx) => (
            <g key={cx} transform={`translate(${cx} 198)`}>
              <circle r="27" fill="#0F1B24" />
              <g className="hero-wheel">
                <circle r="16" fill="#D5DDE2" />
                {[0, 72, 144, 216, 288].map((a) => (
                  <rect key={a} x="-2" y="-15" width="4" height="13" rx="2" fill="#4B5A66" transform={`rotate(${a})`} />
                ))}
                <circle r="4" fill="#0F1B24" />
              </g>
            </g>
          ))}
        </g>
      </svg>
    </div>
  );
}
