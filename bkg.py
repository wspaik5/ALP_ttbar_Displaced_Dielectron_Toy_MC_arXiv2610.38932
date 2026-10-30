"""Toy study: photon conversions (gamma -> e+e- in tracker material) as a background
to displaced light ALP -> e+e- in ttbar events. Barrel only (|eta|<1.2), 13 TeV, 500 fb^-1.
All detector numbers are rough, stated assumptions (see ASSUMPTIONS)."""
import numpy as np
import mag

LUMI = 500.0e3            # pb^-1  (500 fb^-1)
F_BARREL = 0.547          # P(|eta|<1.2) for eta ~ N(0,1.6)
ASSUMPTIONS = dict(
    sigma_ttgamma_pb=1.0,         # sigma(tt+isolated photon, pT>20 GeV), order-of-magnitude
    # (radius mm, thickness in X0 at eta=0, half-width of material band mm)
    material=[(22, 0.003, 0.5),                         # beryllium beam pipe
              (29, 0.02, 3), (68, 0.02, 3), (109, 0.02, 3), (160, 0.02, 3),   # pixel layers
              (185, 0.05, 5),                           # pixel support / service cylinder
              (255, 0.04, 4), (339, 0.04, 4), (418, 0.04, 4), (498, 0.04, 4),  # TIB
              (550, 0.08, 10),                          # TIB/TOB support
              (608, 0.03, 4), (692, 0.03, 4), (780, 0.03, 4)],                 # TOB
    ang_res_pixel=0.3e-3,  # rad, track direction resolution if pair starts before last pixel layer
    ang_res_strip=0.8e-3,  # rad, strip-only tracks
    ms_term=2.0e-3,        # rad*GeV, multiple-scattering term (sigma = ms_term / p)
    p_res=0.02,            # relative momentum resolution
    vtx_res_pixel=1.0,     # mm, radial vertex resolution (conversion-style fit, needs B field)
    vtx_res_strip=3.0,
)
A = ASSUMPTIONS
MAT = np.array([m[0] for m in A['material']], float)
X0 = np.array([m[1] for m in A['material']], float)
HW = np.array([m[2] for m in A['material']], float)


def _unit(v): return v / np.linalg.norm(v, axis=1)[:, None]


def measure(vtx_r, e1, e2, rng):
    """Smear directions/momenta, return measured pair mass [GeV] and measured vertex radius [mm]."""
    pix = vtx_r < 160
    out = []
    for e in (e1, e2):
        p = np.linalg.norm(e, axis=1)
        s = np.sqrt(np.where(pix, A['ang_res_pixel'], A['ang_res_strip'])**2 + (A['ms_term']/p)**2)
        u = _unit(e)
        a = _unit(np.cross(u, np.array([0, 0, 1.0])[None, :] + 1e-9))
        b = np.cross(u, a)
        u2 = _unit(u + a*rng.normal(0, 1, len(p))[:, None]*s[:, None] + b*rng.normal(0, 1, len(p))[:, None]*s[:, None])
        out.append(u2 * (p*(1 + A['p_res']*rng.normal(0, 1, len(p))))[:, None])
    q1, q2 = out
    E1, E2 = np.linalg.norm(q1, axis=1), np.linalg.norm(q2, axis=1)
    m2 = (E1+E2)**2 - ((q1+q2)**2).sum(1)
    m = np.sqrt(np.clip(m2, 0, None))
    r = vtx_r + rng.normal(0, 1, len(vtx_r))*np.where(pix, A['vtx_res_pixel'], A['vtx_res_strip'])
    return m, r


def basic_cuts(r, e1, e2):
    pt1, pt2 = np.hypot(e1[:, 0], e1[:, 1]), np.hypot(e2[:, 0], e2[:, 1])
    return (r > 0.5) & (r < 800) & (np.minimum(pt1, pt2) > 1.0) & (pt1 + pt2 > 20)


def material_veto(r_meas):
    """True if the measured vertex is AWAY from every material band (passes the veto)."""
    sig = np.where(r_meas < 160, A['vtx_res_pixel'], A['vtx_res_strip'])
    d = np.abs(r_meas[:, None] - MAT[None, :]) - HW[None, :]
    return (d > 2*sig[:, None]).all(1)


def signal(m, ctau, n=300_000, seed=11):
    rng = np.random.default_rng(seed)
    vtx, em, ep = mag.make_events(m, ctau, n, seed=seed)
    r = np.hypot(vtx[:, 0], vtx[:, 1])
    mm, rm = measure(r, em, ep, rng)
    w = np.full(len(r), F_BARREL*LUMI/len(r))   # events per pb of sigma x BR
    return dict(r=r, rm=rm, m=mm, base=basic_cuts(r, em, ep), w=w)


def conversions(n=1_500_000, seed=5):
    rng = np.random.default_rng(seed)
    pt = 20 * rng.uniform(0, 1, n)**-0.5          # dsigma/dpT ~ pT^-3 above 20 GeV
    eta = rng.normal(0, 1.6, 3*n); eta = eta[np.abs(eta) < 1.2][:n]; n = len(eta); pt = pt[:n]
    phi = rng.uniform(0, 2*np.pi, n)
    # sequential conversion probability through layers (path length ~ 1/sin(theta) = cosh(eta))
    pconv = 1 - np.exp(-7/9 * X0[None, :] * np.cosh(eta)[:, None])
    surv = np.cumprod(np.hstack([np.ones((n, 1)), 1-pconv[:, :-1]]), 1)
    prob = surv * pconv                                      # P(convert in layer i)
    cum = np.cumsum(prob, 1); u = rng.uniform(0, 1, n)
    layer = (u[:, None] > cum).sum(1)                         # == len(MAT) means no conversion
    conv = layer < len(MAT)
    pt, eta, phi, layer = pt[conv], eta[conv], phi[conv], layer[conv]
    r = MAT[layer] + rng.uniform(-1, 1, len(pt))*HW[layer]
    # energy sharing (Bethe-Heitler-like: dP/dx ~ 1 - 4/3 x(1-x)), via rejection
    x = rng.uniform(0, 1, 4*len(pt)); acc = rng.uniform(0, 1, 4*len(pt)) < 1 - 4/3*x*(1-x)
    x = x[acc][:len(pt)]
    dirv = np.stack([np.cos(phi), np.sin(phi), np.sinh(eta)], 1) / np.cosh(eta)[:, None]
    p = pt*np.cosh(eta)
    e1, e2 = dirv*(x*p)[:, None], dirv*((1-x)*p)[:, None]  # opening angle ~ m_e/E: negligible
    mm, rm = measure(r, e1, e2, rng)
    w = np.full(len(r), A['sigma_ttgamma_pb']*F_BARREL*LUMI/n)
    return dict(r=r, rm=rm, m=mm, base=basic_cuts(r, e1, e2), w=w, n_photons=A['sigma_ttgamma_pb']*F_BARREL*LUMI,
                frac_conv=conv.mean())


def upper_limit(S_per_pb, B):
    """Expected 95% CL limit on sigma x BR [pb] with a crude counting rule."""
    n_up = max(3.0, 2.0*np.sqrt(B))
    return n_up / S_per_pb if S_per_pb > 0 else np.inf


def scan(m, ctau, sig=None, bkg=None):
    sig = sig or signal(m, ctau); bkg = bkg or conversions()
    res = {}
    stages = {'baseline (paper-like cuts)': (sig['base'], bkg['base'])}
    vs, vb = material_veto(sig['rm']), material_veto(bkg['rm'])
    def best_mass(xs, xb):
        """Optimise mass window (lower cut, optional upper cut) on top of extra selections xs/xb.
        The 'no mass cut' option is always allowed, so a mass cut can never make things worse."""
        best = (upper_limit(sig['w'][xs].sum(), bkg['w'][xb].sum()), np.ones(len(xs), bool), np.ones(len(xb), bool))
        for lo in np.linspace(0, 1.5*m, 31):
            for hi in (3*m + 0.01, np.inf):
                ms = (sig['m'] > lo) & (sig['m'] < hi); mb = (bkg['m'] > lo) & (bkg['m'] < hi)
                lim = upper_limit(sig['w'][xs & ms].sum(), bkg['w'][xb & mb].sum())
                if lim < best[0]: best = (lim, ms, mb)
        return best[1], best[2]
    ms, mb = best_mass(sig['base'], bkg['base'])
    stages['+ mass window'] = (sig['base'] & ms, bkg['base'] & mb)
    stages['+ material veto'] = (sig['base'] & vs, bkg['base'] & vb)
    ms2, mb2 = best_mass(sig['base'] & vs, bkg['base'] & vb)
    stages['+ mass window + material veto'] = (sig['base'] & ms2 & vs, bkg['base'] & mb2 & vb)
    lo = None
    stages['inside beam pipe only (r<20 mm)'] = (sig['base'] & (sig['rm'] < 20), bkg['base'] & (bkg['rm'] < 20))
    for k, (cs, cb) in stages.items():
        S, B = sig['w'][cs].sum(), bkg['w'][cb].sum()
        res[k] = dict(eff=cs.mean()*100, B=B, limit=upper_limit(S, B))
    S0 = sig['w'][sig['base']].sum()
    res['no conversion background'] = dict(eff=sig['base'].mean()*100, B=0.0, limit=upper_limit(S0, 0))
    return res, lo
