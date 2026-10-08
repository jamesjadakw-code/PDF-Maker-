/* BAM listing thumbnail cities. Stable per unit. Off the brochure. */
(function () {
  var CORE = [
    "Houston, TX",
    "Orlando, FL",
    "Atlanta, GA",
    "Oklahoma City, OK",
    "Las Vegas, NV",
    "Miami, FL",
    "Dallas, TX",
    "Savannah, GA",
    "Tulsa, OK",
    "Reno, NV",
    "Austin, TX",
    "Tampa, FL",
    "Augusta, GA",
    "Norman, OK",
    "Henderson, NV",
    "San Antonio, TX",
    "Jacksonville, FL",
    "Macon, GA",
    "Lawton, OK",
    "North Las Vegas, NV",
    "Fort Worth, TX",
    "Tallahassee, FL",
    "Columbus, GA",
    "Broken Arrow, OK",
    "Carson City, NV",
    "El Paso, TX",
    "Fort Lauderdale, FL",
    "Athens, GA",
    "Edmond, OK",
    "Sparks, NV",
    "Arlington, TX",
    "St. Petersburg, FL",
    "Sandy Springs, GA",
    "Moore, OK",
    "Elko, NV",
    "Corpus Christi, TX",
    "West Palm Beach, FL",
    "Roswell, GA",
    "Enid, OK",
    "Mesquite, NV",
    "Plano, TX",
    "Gainesville, FL",
    "Johns Creek, GA",
    "Midwest City, OK",
    "Boulder City, NV",
    "Lubbock, TX",
    "Ocala, FL",
    "Warner Robins, GA",
    "Stillwater, OK",
    "Pahrump, NV",
    "Laredo, TX",
    "Sarasota, FL",
    "Alpharetta, GA",
    "Muskogee, OK",
    "Fernley, NV",
    "Amarillo, TX",
    "Pensacola, FL",
    "Marietta, GA",
    "Bartlesville, OK",
    "Winnemucca, NV",
    "Lynchburg, VA",
    "Charleston, SC",
    "Birmingham, AL",
    "Nashville, TN",
    "Charlotte, NC",
    "Little Rock, AR",
    "Baton Rouge, LA",
    "Jackson, MS",
    "Louisville, KY",
    "Mobile, AL"
  ];
  var OTHER = [
    "Phoenix, AZ",
    "Denver, CO",
    "Seattle, WA",
    "Chicago, IL",
    "Boston, MA",
    "Columbus, OH",
    "Indianapolis, IN",
    "Detroit, MI",
    "Milwaukee, WI",
    "Minneapolis, MN",
    "Kansas City, MO",
    "Omaha, NE",
    "Wichita, KS",
    "Salt Lake City, UT",
    "Boise, ID",
    "Portland, OR",
    "San Diego, CA",
    "Sacramento, CA",
    "Philadelphia, PA",
    "Newark, NJ",
    "Baltimore, MD",
    "Buffalo, NY",
    "Hartford, CT",
    "Providence, RI",
    "Manchester, NH",
    "Burlington, VT",
    "Portland, ME",
    "Albuquerque, NM",
    "Cheyenne, WY",
    "Billings, MT"
  ];
  var EVERY = 18;

  function cityHash(key) {
    var h = 2166136261, s = String(key || "");
    for (var i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function cityFor(key) {
    var h = cityHash(key);
    if (h % EVERY === 0) return OTHER[h % OTHER.length];
    return CORE[Math.floor(h / EVERY) % CORE.length];
  }

  function css() {
    if (document.getElementById("bam-card-loc-css")) return;
    var s = document.createElement("style");
    s.id = "bam-card-loc-css";
    s.textContent = ".unit-card .card-img .card-loc{position:absolute;left:10px;bottom:10px;z-index:2;background:rgba(0,0,0,.72);color:#fff;font-size:12px;font-weight:800;line-height:1.2;padding:4px 9px;border-radius:5px;letter-spacing:.01em;max-width:calc(100% - 96px);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;pointer-events:none}";
    document.head.appendChild(s);
  }

  function paint(root) {
    (root || document).querySelectorAll(".unit-card[data-live-key]").forEach(function (card) {
      var img = card.querySelector(".card-img");
      if (!img) return;
      var el = img.querySelector(".card-loc");
      if (!el) {
        el = document.createElement("span");
        el.className = "card-loc";
        img.appendChild(el);
      }
      el.textContent = cityFor(card.getAttribute("data-live-key"));
    });
  }

  function run() {
    css();
    paint(document);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run);
  else run();
  document.addEventListener("bam:live", run);
  window.BAMListingCity = { cityFor: cityFor, paint: paint };
})();
