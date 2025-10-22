
// Rotator with CTA style sync
const cardPaths = ["img/card1.jpg", "img/card2.jpg", "img/card3.jpg", "img/card4.jpg"];
let idx = 0;
function rotateCard(){
  const img = document.getElementById("rotating-card");
  const cta = document.getElementById("rotator-cta");
  if(!img || !cta) return;
  idx = (idx + 1) % cardPaths.length;
  img.src = `/static/${cardPaths[idx]}`;
  cta.classList.toggle("btn-primary");
  cta.classList.toggle("btn-ghost");
}
setInterval(rotateCard, 3000);

// Live stats refresh (in case orders created during session)
async function refreshStats(){
  try{
    const res = await fetch("/api/stats");
    const data = await res.json();
    if(data.ok){
      const t = document.getElementById("stat-total");
      const g = document.getElementById("stat-gem10");
      if(t) t.textContent = data.total;
      if(g) g.textContent = data.gem10;
    }
  }catch(e){}
}
setInterval(refreshStats, 15000);

// AI pre-check
const aiForm = document.getElementById("ai-form");
if (aiForm){
  aiForm.addEventListener("submit", async (e)=>{
    e.preventDefault();
    const fileInput = document.getElementById("cardImage");
    const out = document.getElementById("ai-result");
    out.classList.add("hidden");
    out.innerHTML = "";
    if (!fileInput.files.length){ return; }
    const fd = new FormData();
    fd.append("image", fileInput.files[0]);
    try{
      const res = await fetch("/api/grade", { method:"POST", body:fd });
      const data = await res.json();
      if(!data.ok){ throw new Error(data.error || "AI error"); }
      out.classList.remove("hidden");
      out.innerHTML = `
        <h3>AI Assessment</h3>
        <p><strong>Grade:</strong> ${data.grade}</p>
        <ul>
          <li>Centering: ${data.subgrades.centering}</li>
          <li>Corners: ${data.subgrades.corners}</li>
          <li>Edges: ${data.subgrades.edges}</li>
          <li>Surface: ${data.subgrades.surface}</li>
        </ul>
      `;
      window._aiSubgrades = data.subgrades;
      window._aiGrade = data.grade;
    }catch(err){
      out.classList.remove("hidden");
      out.innerHTML = `<p>Error: ${err.message}</p>`;
    }
  });
}

// Create order
const orderBtn = document.getElementById("create-order");
if (orderBtn){
  orderBtn.addEventListener("click", async ()=>{
    const form = document.getElementById("order-form");
    const fd = new FormData(form);
    const payload = {
      name: fd.get("name"),
      email: fd.get("email"),
      service: fd.get("service"),
      title: fd.get("title"),
      grade: window._aiGrade || "Pending",
      subgrades: window._aiSubgrades || {}
    };
    const out = document.getElementById("order-out");
    out.classList.add("hidden"); out.innerHTML = "";
    try{
      const res = await fetch("/api/order", {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if(!data.ok){ throw new Error(data.error || "Order error"); }
      out.classList.remove("hidden");
      out.innerHTML = `
        <h3>Order Created</h3>
        <p>Cert: <strong>${data.cert}</strong></p>
        <p><a class="btn btn-primary" href="${data.cert_url}" target="_blank">View Certificate</a></p>
        <p><a class="btn btn-ghost" href="${data.qr_url}" download>Download QR</a></p>
        <p><a class="btn btn-ghost" href="${data.label_url}" download>Download Label</a></p>
        <p><a class="btn btn-ghost" href="${data.pdf_url}" download>Download PDF</a></p>
      `;
      refreshStats();
    }catch(err){
      out.classList.remove("hidden");
      out.innerHTML = `<p>Error: ${err.message}</p>`;
    }
  });
}

// Lookup
const lookupForm = document.getElementById("lookup-form");
if (lookupForm){
  lookupForm.addEventListener("submit", async (e)=>{
    e.preventDefault();
    const cert = document.getElementById("cert").value.trim();
    const out = document.getElementById("lookup-result");
    out.classList.add("hidden");
    out.innerHTML = "";
    if(!cert){ return; }
    try{
      const res = await fetch(`/api/lookup?cert=${encodeURIComponent(cert)}`);
      const data = await res.json();
      if(!data.ok){ throw new Error(data.error || "Lookup error"); }
      const sub = data.subgrades || {};
      const pop = data.pop || {};
      const popList = Object.keys(pop).map(g => `<li>${g}: ${pop[g]}</li>`).join("");
      out.classList.remove("hidden");
      out.innerHTML = `
        <h3>Certification #${data.cert}</h3>
        <p>${data.title || "N/A"}</p>
        <p><strong>Grade:</strong> ${data.grade}</p>
        <p><strong>Subgrades:</strong> C ${sub.centering||""} • Co ${sub.corners||""} • E ${sub.edges||""} • S ${sub.surface||""}</p>
        <h4>Pop Report</h4>
        <ul>${popList || "<li>No data yet</li>"}</ul>
      `;
    }catch(err){
      out.classList.remove("hidden");
      out.innerHTML = `<p>Error: ${err.message}</p>`;
    }
  });
}

// Registry submit
const regBtn = document.getElementById("reg-submit");
if (regBtn){
  regBtn.addEventListener("click", async ()=>{
    const form = document.getElementById("reg-form");
    const fd = new FormData(form);
    const payload = {
      cert: fd.get("cert"),
      display_name: fd.get("display_name"),
      note: fd.get("note"),
    };
    try{
      const res = await fetch("/api/registry", {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if(!data.ok){ alert(data.error || "Error"); return; }
      location.reload();
    }catch(e){ alert("Error submitting registry"); }
  });
}
