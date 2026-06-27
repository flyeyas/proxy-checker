def serve_flask_http(app_factory, *, port, threads, logger):
    try:
        from waitress import serve
    except ImportError as exc:
        logger.critical("Waitress is required to run the HTTP server; install it with 'pip install -r requirements.txt'")
        raise SystemExit(1) from exc

    app = app_factory()
    logger.info(f"ProxyForge Flask server running at http://0.0.0.0:{port}")
    logger.info(f"HTTP threads: {threads}")
    serve(app, host="0.0.0.0", port=port, threads=threads)
