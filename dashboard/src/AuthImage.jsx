import React, { useState, useEffect } from 'react';
import api from './api';

// Plain <img src="..."> tags can't attach an Authorization header, but
// /api/image/:file_id now requires one. This component fetches the image
// through the shared authenticated `api` instance as a blob and renders it
// via an object URL instead.
const AuthImage = ({ src, alt, className }) => {
    const [imgSrc, setImgSrc] = useState(null);
    const [failed, setFailed] = useState(false);

    useEffect(() => {
        let objectUrl = null;
        let cancelled = false;

        setImgSrc(null);
        setFailed(false);

        api.get(src, { responseType: 'blob' })
            .then((res) => {
                if (cancelled) return;
                objectUrl = URL.createObjectURL(res.data);
                setImgSrc(objectUrl);
            })
            .catch(() => {
                if (!cancelled) setFailed(true);
            });

        return () => {
            cancelled = true;
            if (objectUrl) URL.revokeObjectURL(objectUrl);
        };
    }, [src]);

    if (failed || !src) {
        return (
            <div className="h-full w-full bg-gray-100 rounded flex items-center justify-center text-gray-300">
                <span className="text-xs">No Img</span>
            </div>
        );
    }

    if (!imgSrc) {
        return (
            <div className="h-full w-full bg-gray-100 rounded animate-pulse" />
        );
    }

    return (
        <img
            src={imgSrc}
            alt={alt}
            className={className}
            loading="lazy"
        />
    );
};

export default AuthImage;
