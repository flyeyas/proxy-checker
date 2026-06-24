def serve_legacy_http(port, handler_factory, logger, server_class):
    server = server_class(("0.0.0.0", port), handler_factory(), logger=logger)
    logger.info(f"Proxy Checker legacy HTTP server running at http://0.0.0.0:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopped.")
        server.server_close()
    except Exception as exc:
        logger.critical(f"Server crashed: {exc}", exc_info=True)


def serve_flask_http(app_factory, *, port, threads, logger, legacy_server):
    try:
        from waitress import serve
    except ImportError:
        logger.warning("Waitress not installed; falling back to legacy HTTP server")
        legacy_server()
        return

    app = app_factory()
    logger.info(f"Proxy Checker Flask server running at http://0.0.0.0:{port}")
    logger.info(f"HTTP threads: {threads}")
    serve(app, host="0.0.0.0", port=port, threads=threads)
