describe("Windows 安装包", () => {
  it("可以完成首次模型配置并读取两个本地资料库", async () => {
    const body = await $("body");
    await body.waitForExist({ timeout: 120_000 });

    await browser.waitUntil(
      async () => {
        const text = await $("body").getText();
        if (text.includes("本地服务未连接")) {
          throw new Error(`本地服务启动失败：${text}`);
        }
        return !text.includes("正在启动本地服务并准备资料…");
      },
      {
        timeout: 180_000,
        interval: 500,
        timeoutMsg: "本地服务在 180 秒内未完成首次启动",
      },
    );

    const initialText = await $("body").getText();
    expect(
      initialText.includes("先连接你的模型") || initialText.includes("命册尚空"),
    ).toBe(true);

    if (initialText.includes("先连接你的模型")) {
      const inputs = await $$("form input");
      await inputs[0].setValue("http://127.0.0.1:18768/v1");
      await inputs[1].setValue("windows-e2e-model");
      await inputs[2].setValue("windows-e2e-key");
      await $("button=保存并进入命册").click();
    }

    await $("h1=命册尚空").waitForExist({ timeout: 180_000 });
    await $("button[aria-label='资料库']").click();

    const dialog = await $("[role='dialog']");
    await dialog.waitForExist();
    expect(await dialog.getText()).toContain("知命内置知识");

    await $("button=命例库").click();
    expect(await dialog.getText()).toContain("知命内置命例");
  });
});
