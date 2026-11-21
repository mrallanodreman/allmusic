const asset = (name) => `${import.meta.env.BASE_URL}assets/radio-ui/${name}`;

export function DecorLayer() {
  return (
    <div className="decor-layer" aria-hidden="true">
      <img className="decor decor--tape" src={asset('tape_en_vivo.png')} alt="" />
      <img className="decor decor--crosshair" src={asset('emblem_target_crosshair.png')} alt="" />
      <img className="decor decor--stay" src={asset('sticker_stay_tuned.png')} alt="" />
      <img className="decor decor--halftone" src={asset('texture_halftone_overlay.png')} alt="" />
    </div>
  );
}
