import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display';

export async function createRenderer() {
    // Restore the native 5000x5000 PIXI canvas setup from the working version
    const app = new PIXI.Application({
        width: 5000,
        height: 5000,
        backgroundAlpha: 0,
        preserveDrawingBuffer: false,
        resolution: 1,
        hello: true
    });

    // PIXI 7 Settings
    PIXI.settings.PRECISION_FRAGMENT = 'highp';
    PIXI.settings.PREFER_CREATE_IMAGE_BITMAP = false;

    document.body.appendChild(app.view);
    return app;
}

export async function renderToStage(app, modelSettings, modelUrl) {
    console.log('[Renderer] Loading Live2DModel...');

    modelSettings.url = modelUrl;

    const model = await Live2DModel.from(modelSettings, {
        autoUpdate: true
    });

    model.premultipliedAlpha = true;
    app.stage.addChild(model);
    model.update(0);

    const bounds = model.getLocalBounds();
    console.log(`[Renderer] Bounds: ${bounds.width.toFixed(0)}x${bounds.height.toFixed(0)}`);

    // Target 40% of the 5000px canvas (exact math from working f2dbf5e6)
    const targetSize = 5000 * 0.4;
    const scale = Math.min(targetSize / bounds.width, targetSize / bounds.height);

    model.scale.set(scale);

    // Center model relative to the 5000x5000 canvas bounds
    model.x = (5000 / 2) - (bounds.x + bounds.width / 2) * scale;
    model.y = (5000 / 2) - (bounds.y + bounds.height / 2) * scale;

    model.filterArea = app.screen;
    return model;
}

export async function finalizeRender(app, model) {
    return new Promise((resolve) => {
        // Exact original render timing setup
        setTimeout(() => {
            model.update(16);
            app.renderer.render(app.stage);

            setTimeout(() => {
                model.update(16);
                app.renderer.render(app.stage);
                console.log('[Renderer] Final frames rendered.');
                resolve();
            }, 50);
        }, 200);
    });
}
